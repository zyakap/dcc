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
