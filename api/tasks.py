from celery import shared_task

from .sync import sync_all_tenants


@shared_task
def sync_tenant_feeds():
    """Scheduled pull of every feed-enabled tenant's LMS data into DCC."""
    results = sync_all_tenants()
    return results


@shared_task
def auto_send_invoices():
    """Daily check: on the configured send day (SaaS Admin -> Invoices), when
    auto-send is enabled, generate and email last month's invoice to every
    active tenant. Idempotent — tenants already emailed are skipped."""
    import datetime

    from django.utils import timezone

    from users.models import UserProfile

    from .models import BillingSettings, generate_invoice, send_invoice

    billing = BillingSettings.current()
    if not billing.auto_send_enabled:
        return {'sent': 0, 'skipped': 'auto-send disabled'}
    today = timezone.localdate()
    if today.day != billing.send_day:
        return {'sent': 0, 'skipped': f'not send day ({billing.send_day})'}

    prev = today.replace(day=1) - datetime.timedelta(days=1)
    sent = errors = 0
    for tenant in UserProfile.objects.filter(use_loanmasta=True):
        invoice = generate_invoice(tenant, prev.year, prev.month)
        if invoice.sent_at is not None:
            continue
        try:
            send_invoice(invoice, cc_email=billing.cc_email)
            sent += 1
        except Exception:
            errors += 1
    return {'sent': sent, 'errors': errors, 'period': f'{prev.year}-{prev.month:02d}'}


@shared_task
def recompute_credit_scores():
    """Nightly pass over the whole database: recompute the benchmark credit
    score for every client from their loans, transactions and full profile
    history, so ratings stay current even for clients nobody has paid to
    view recently."""
    from client.models import ClientProfile, ClientCreditScore, matched_profiles

    done = set()
    computed = 0
    for profile in ClientProfile.objects.all().only('id').iterator():
        if profile.id in done:
            continue
        profiles = matched_profiles(ClientProfile.objects.filter(pk=profile.id))
        primary = sorted(profiles, key=lambda p: p.updated_at or p.created_at, reverse=True)[0]
        ClientCreditScore.ensure(primary, profiles=profiles)
        done.update(p.id for p in profiles)
        computed += 1
    return {'persons_scored': computed, 'profiles_covered': len(done)}


@shared_task
def expire_old_defaults():
    """Monthly: archive ClientProfile defaults older than PlatformSettings.default_expiry_years.

    Sets dcc_status to 'SETTLED' and dcc_flagged to False, preserving the history
    entry via ClientProfileHistory so the expiry is auditable."""
    import datetime
    from django.utils import timezone
    from .models import PlatformSettings
    from client.models import ClientProfile, DefaultNotice

    settings_obj = PlatformSettings.current()
    cutoff_years = settings_obj.default_expiry_years or 7
    cutoff_date  = timezone.now() - datetime.timedelta(days=cutoff_years * 365)

    # Find notices older than the retention period that are still LISTED
    old_notices = DefaultNotice.objects.filter(
        status='LISTED',
        listed_at__lt=cutoff_date,
    ).select_related('client')

    archived = 0
    for notice in old_notices:
        notice.status = 'SETTLED'
        notice.settled_at = timezone.now()
        notice.notes = (notice.notes or '') + f'\n[Auto-archived after {cutoff_years}y retention period]'
        notice.save(update_fields=['status', 'settled_at', 'notes'])

        client = notice.client
        # Only update if no other active listed notice exists
        still_active = DefaultNotice.objects.filter(client=client, status='LISTED').exclude(pk=notice.pk).exists()
        if not still_active:
            client.dcc_status  = 'SETTLED'
            client.dcc_flagged = False
            client.save(update_fields=['dcc_status', 'dcc_flagged'])
        archived += 1

    return {'archived_notices': archived, 'cutoff_years': cutoff_years}


@shared_task
def send_watch_digest():
    """Monday 7 AM: for every tenant on WEEKLY digest mode, collect all
    un-emailed ClientWatchEvent rows and send one consolidated email.
    Skips tenants with no pending events."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail
    from django.utils import timezone
    from client.models import ClientWatchEvent, ClientWatch
    from users.models import UserProfile

    now = timezone.now()
    sent = 0

    for tenant in UserProfile.objects.filter(watch_digest_mode='WEEKLY'):
        email = getattr(tenant, 'work_email', None) or getattr(tenant, 'email', None)
        if not email:
            continue

        # Collect events not yet sent in a digest
        events = (ClientWatchEvent.objects
                  .filter(watch__tenant=tenant, digest_sent_at__isnull=True)
                  .select_related('watch__client')
                  .order_by('fired_at'))
        if not events.exists():
            continue

        # Group by client
        from collections import defaultdict
        by_client = defaultdict(list)
        for ev in events:
            by_client[ev.watch.client].append(ev)

        domain = getattr(dj_settings, 'DOMAIN', 'https://dc.com.pg')
        lines = [f'Weekly Watch List Digest — {now:%d %b %Y}\n']
        lines.append(f'Dear {tenant.organisation or tenant.first_name},\n')
        lines.append(f'The following clients on your Watch List had changes this week:\n')
        for client, evs in by_client.items():
            all_types = sorted({t for ev in evs for t in ev.alert_types})
            lines.append(
                f'  • {client.first_name} {client.last_name}  (CUID: {client.CUID or "—"})\n'
                f'    Changes: {", ".join(all_types)}\n'
                f'    View: {domain}/client/view/{client.id}/\n'
            )

        lines.append(f'\nTotal alerts this week: {len(events)}\n')
        lines.append(f'Credit file views are billed at your plan rate.\n')
        lines.append(f'\n— DCC Dinau Control Center')

        try:
            send_mail(
                subject=f'DCC Weekly Watch Digest — {now:%d %b %Y}',
                message='\n'.join(lines),
                from_email=dj_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            events.update(digest_sent_at=now)
            sent += 1
        except Exception:
            pass

    return {'digests_sent': sent}


@shared_task
def check_dispute_slas():
    """Daily 8 AM: escalate disputes that have breached their 5-business-day SLA
    and haven't been resolved. Sends a notification to SaaS admin and the filing
    tenant."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail
    from django.utils import timezone
    from client.models import Dispute

    now = timezone.now()
    breached = Dispute.objects.filter(
        sla_deadline__lt=now,
        status__in=('OPEN', 'UNDER_REVIEW'),
        escalated_at__isnull=True,
    ).select_related('client', 'filed_by_tenant')

    escalated = 0
    for dispute in breached:
        dispute.status = 'ESCALATED'
        dispute.escalated_at = now
        dispute.save(update_fields=['status', 'escalated_at'])

        domain = getattr(dj_settings, 'DOMAIN', 'https://dc.com.pg')
        admin_email = dj_settings.DEFAULT_FROM_EMAIL

        body = (
            f'Dispute #{dispute.pk} has breached its 5-business-day SLA.\n\n'
            f'Client: {dispute.client.first_name} {dispute.client.last_name}  '
            f'(CUID: {dispute.client.CUID or "—"})\n'
            f'Type: {dispute.get_dispute_type_display()}\n'
            f'Filed: {dispute.created_at:%d %b %Y}\n'
            f'SLA Deadline: {dispute.sla_deadline:%d %b %Y %H:%M}\n\n'
            f'Review: {domain}/saasadmin/disputes/\n\n'
            f'— DCC Auto-Escalation System'
        )

        recipients = [admin_email]
        if dispute.filed_by_tenant:
            tenant_email = (getattr(dispute.filed_by_tenant, 'work_email', None)
                            or getattr(dispute.filed_by_tenant, 'email', None))
            if tenant_email and tenant_email != admin_email:
                recipients.append(tenant_email)

        try:
            send_mail(
                subject=f'[ESCALATED] Dispute #{dispute.pk} — SLA breached',
                message=body,
                from_email=admin_email,
                recipient_list=recipients,
                fail_silently=True,
            )
        except Exception:
            pass
        escalated += 1

    return {'escalated': escalated}
