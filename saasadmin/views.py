import datetime
import decimal
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Avg, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from api.models import (
    ApiUsageLog, BillingSettings, CreditCheckAccess, Invoice, PlatformSettings, PricingSettings,
    generate_invoice, send_invoice, usage_summary,
)
from api.sync import sync_all_tenants
from client.models import (
    ClientCreditScore, ClientProfile, DefaultNotice, Dispute, IdentityCase, IdentityExclusion,
    RatingRule, matched_profiles, merge_profiles, scan_identity_cases,
)
from loan.models import Loan
from users.models import User, UserProfile


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def superuser_required(view_fn):
    """Decorator: only allow active superusers; otherwise redirect to login."""
    @login_required(login_url='/users/login_user/')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'Superuser access required.', extra_tags='danger')
            return redirect('/')
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


# ---------------------------------------------------------------------------
# Sync all
# ---------------------------------------------------------------------------

@superuser_required
@require_POST
def sa_sync_all(request):
    """Trigger a live sync of all feed-enabled tenants and report results."""
    results = sync_all_tenants()
    ok = sum(1 for r in results if r['ok'])
    failed = [r for r in results if not r['ok']]
    total_profiles = sum(r.get('profiles', 0) for r in results)
    total_loans = sum(r.get('loans', 0) for r in results)
    total_statements = sum(r.get('statements', 0) for r in results)

    if not results:
        messages.warning(request, 'No feed-enabled tenants with API keys found — nothing synced.', extra_tags='warning')
    else:
        messages.success(
            request,
            f'Sync complete: {ok}/{len(results)} tenants OK — '
            f'{total_profiles} profiles, {total_loans} loans, {total_statements} statements ingested.',
            extra_tags='info',
        )
        for r in failed:
            messages.error(request, f'Sync failed for {r["tenant"]}: {r["error"]}', extra_tags='danger')

    return redirect('sa_dashboard')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@superuser_required
def sa_dashboard(request):
    today = datetime.date.today()

    total_tenants = UserProfile.objects.filter(use_loanmasta=True).count()
    active_tenants = UserProfile.objects.filter(use_loanmasta=True, user__active=True).count()
    total_clients = ClientProfile.objects.count()
    total_loans = Loan.objects.count()

    # Month activity
    month_clients = ClientProfile.objects.filter(
        created_at__year=today.year, created_at__month=today.month).count()
    month_loans = Loan.objects.filter(
        created_at__year=today.year, created_at__month=today.month).count()

    # Loan financial snapshot
    loan_agg = Loan.objects.aggregate(
        total_outstanding=Sum('total_outstanding'),
        total_arrears=Sum('total_arrears'),
    )

    # DCC credit-check activity this month
    pricing = PricingSettings.current()
    month_logs = ApiUsageLog.objects.filter(
        created_at__year=today.year, created_at__month=today.month)
    month_credit_checks = month_logs.filter(action='CREDIT_CHECK').aggregate(n=Sum('units'))['n'] or 0
    month_revenue = pricing.price_per_credit_check * month_credit_checks

    # Tenants with DCC enabled
    dcc_enabled_count = UserProfile.objects.filter(use_loanmasta=True, credit_check_enabled=True).count()

    # Recent tenants
    recent_tenants = UserProfile.objects.filter(use_loanmasta=True).order_by('-date_joined')[:5]

    context = {
        'nav': 'sa_dashboard',
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'total_clients': total_clients,
        'total_loans': total_loans,
        'month_clients': month_clients,
        'month_loans': month_loans,
        'loan_outstanding': loan_agg['total_outstanding'] or 0,
        'loan_arrears': loan_agg['total_arrears'] or 0,
        'month_credit_checks': month_credit_checks,
        'month_revenue': month_revenue,
        'dcc_enabled_count': dcc_enabled_count,
        'pricing': pricing,
        'recent_tenants': recent_tenants,
        'today': today,
    }
    return render(request, 'saasadmin/dashboard.html', context)


# ---------------------------------------------------------------------------
# Tenant management
# ---------------------------------------------------------------------------

@superuser_required
def sa_tenants(request):
    query = request.GET.get('q', '').strip()
    plan_filter = request.GET.get('plan', '').strip()

    tenants = UserProfile.objects.filter(use_loanmasta=True).select_related('user').order_by('organisation')

    if query:
        tenants = tenants.filter(
            Q(organisation__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(LUID__icontains=query) |
            Q(endpoint__icontains=query) |
            Q(work_email__icontains=query)
        )
    if plan_filter:
        tenants = tenants.filter(plan=plan_filter)

    tenants = list(tenants)
    for t in tenants:
        t.dcc_client_count = ClientProfile.objects.filter(user_profile=t).count()
        t.dcc_loan_count = Loan.objects.filter(lender=t).count()

    context = {
        'nav': 'sa_tenants',
        'tenants': tenants,
        'query': query,
        'plan_filter': plan_filter,
        'plan_choices': UserProfile.PLAN_CHOICES,
    }
    return render(request, 'saasadmin/tenants.html', context)


@superuser_required
def sa_tenant_detail(request, tenant_id):
    tenant = get_object_or_404(UserProfile.objects.select_related('user'), pk=tenant_id)
    today = datetime.date.today()

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'regen_key':
            tenant.api_key = secrets.token_hex(32)
            tenant.save()
            messages.success(request, 'API key regenerated.', extra_tags='info')
            return redirect('sa_tenant_detail', tenant_id=tenant.id)

        # Save config
        tenant.endpoint = request.POST.get('endpoint', tenant.endpoint).strip()
        tenant.LUID = request.POST.get('LUID', tenant.LUID).strip()
        tenant.organisation = request.POST.get('organisation', tenant.organisation)
        if request.POST.get('plan') in dict(UserProfile.PLAN_CHOICES):
            tenant.plan = request.POST.get('plan')
        tenant.feed_enabled = request.POST.get('feed_enabled') == 'on'
        tenant.credit_check_enabled = request.POST.get('credit_check_enabled') == 'on'
        tenant.can_view_loans = request.POST.get('can_view_loans') == 'on'
        tenant.can_view_transactions = request.POST.get('can_view_transactions') == 'on'
        tenant.can_view_uploads = request.POST.get('can_view_uploads') == 'on'
        try:
            tenant.credit_check_window_hours = int(request.POST.get('credit_check_window_hours', 12))
        except (ValueError, TypeError):
            pass
        tenant.save()
        messages.success(request, 'Tenant configuration saved.', extra_tags='info')
        return redirect('sa_tenant_detail', tenant_id=tenant.id)

    # Usage stats for this tenant (all metered actions, not just credit checks)
    summary = usage_summary(tenant, today.year, today.month)
    pricing = summary['pricing']
    month_checks = next((r['units'] for r in summary['rows'] if r['action'] == 'CREDIT_CHECK'), 0)
    month_cost = summary['total']

    client_count = ClientProfile.objects.filter(user_profile=tenant).count()
    loan_count = Loan.objects.filter(lender=tenant).count()

    context = {
        'nav': 'sa_tenants',
        'tenant': tenant,
        'plan_choices': UserProfile.PLAN_CHOICES,
        'pricing': pricing,
        'month_checks': month_checks,
        'month_cost': month_cost,
        'client_count': client_count,
        'loan_count': loan_count,
        'today': today,
    }
    return render(request, 'saasadmin/tenant_detail.html', context)


@superuser_required
def sa_tenant_create(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        organisation = request.POST.get('organisation', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        LUID = request.POST.get('LUID', '').strip()
        endpoint = request.POST.get('endpoint', '').strip()
        plan = request.POST.get('plan', 'BASIC')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already in use.', extra_tags='danger')
            return render(request, 'saasadmin/tenant_create.html', {'nav': 'sa_tenants', 'plan_choices': UserProfile.PLAN_CHOICES, 'post': request.POST})

        username = email.split('@')[0]
        base = username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f'{base}{suffix}'
            suffix += 1

        user = User.objects.create_user(email=email, username=username, password=password, is_active=True)
        user.active = True
        user.staff = True
        user.save()

        api_key = secrets.token_hex(32)
        UserProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            organisation=organisation,
            LUID=LUID,
            endpoint=endpoint or 'www.loanmasta.com',
            plan=plan if plan in dict(UserProfile.PLAN_CHOICES) else 'BASIC',
            use_loanmasta=True,
            api_key=api_key,
        )
        messages.success(request, f'Tenant "{organisation or email}" created.', extra_tags='info')
        return redirect('sa_tenants')

    context = {
        'nav': 'sa_tenants',
        'plan_choices': UserProfile.PLAN_CHOICES,
    }
    return render(request, 'saasadmin/tenant_create.html', context)


@superuser_required
@require_POST
@superuser_required
@require_POST
def sa_sync_tenant(request, tenant_id):
    from api.sync import sync_tenant
    tenant = get_object_or_404(UserProfile, pk=tenant_id)
    result = sync_tenant(tenant)
    if result['ok']:
        messages.success(
            request,
            f"Sync complete: {result['profiles']} profiles, {result['loans']} loans, "
            f"{result['statements']} statements.",
            extra_tags='info')
    else:
        messages.error(request, f"Sync failed: {result['error']}", extra_tags='danger')
    next_url = request.POST.get('next', '')
    if next_url == 'list':
        return redirect('sa_tenants')
    return redirect('sa_tenant_detail', tenant_id=tenant.id)


@superuser_required
def sa_tenant_toggle_active(request, tenant_id):
    tenant = get_object_or_404(UserProfile.objects.select_related('user'), pk=tenant_id)
    user = tenant.user
    user.active = not user.active
    user.save()
    state = 'activated' if user.active else 'suspended'
    messages.success(request, f'Tenant {tenant} {state}.', extra_tags='info')
    return redirect('sa_tenant_detail', tenant_id=tenant.id)


@superuser_required
@require_POST
def sa_tenant_delete(request, tenant_id):
    tenant = get_object_or_404(UserProfile.objects.select_related('user'), pk=tenant_id)
    name = str(tenant)
    user = tenant.user
    tenant.delete()
    user.delete()
    messages.success(request, f'Tenant "{name}" deleted.', extra_tags='info')
    return redirect('sa_tenants')


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

@superuser_required
def sa_billing(request):
    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    pricing = PricingSettings.current()
    logs = ApiUsageLog.objects.filter(created_at__year=year, created_at__month=month)

    rows = []
    grand_total = decimal.Decimal('0.00')
    for tenant in UserProfile.objects.filter(use_loanmasta=True).order_by('organisation'):
        tl = logs.filter(tenant=tenant)
        usage = {}
        for action, _ in ApiUsageLog.ACTION_CHOICES:
            usage[action] = tl.filter(action=action).aggregate(n=Sum('units'))['n'] or 0
        cost = pricing.monthly_base_fee
        for action, units in usage.items():
            cost += ApiUsageLog.cost_for(action, units, pricing)
        grand_total += cost
        rows.append({
            'tenant': tenant,
            'credit_checks': usage.get('CREDIT_CHECK', 0),
            'profile_lookups': usage.get('PROFILE_LOOKUP', 0) + usage.get('LOANS_LOOKUP', 0) + usage.get('TRANSACTIONS_LOOKUP', 0),
            'feed_records': usage.get('FEED_SYNC', 0),
            'base_fee': pricing.monthly_base_fee,
            'cost': cost,
        })

    context = {
        'nav': 'sa_billing',
        'rows': rows,
        'grand_total': grand_total,
        'pricing': pricing,
        'year': year,
        'month': month,
        'months': [(m, datetime.date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        'years': list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'saasadmin/billing.html', context)


@superuser_required
def sa_pricing(request):
    pricing = PricingSettings.current()

    if request.method == 'POST':
        if pricing.pk is None:
            pricing = PricingSettings()
        for field in ('monthly_base_fee', 'price_per_credit_check',
                      'price_per_profile_lookup', 'price_per_record_synced'):
            val = request.POST.get(field)
            if val not in (None, ''):
                try:
                    setattr(pricing, field, decimal.Decimal(val))
                except Exception:
                    pass
        pricing.currency = request.POST.get('currency', pricing.currency) or pricing.currency
        pricing.save()
        messages.success(request, 'Pricing updated.', extra_tags='info')
        return redirect('sa_pricing')

    context = {
        'nav': 'sa_billing',
        'pricing': pricing,
    }
    return render(request, 'saasadmin/pricing.html', context)


@superuser_required
def sa_tenant_usage(request, tenant_id):
    """Pay-per-view drilldown for one tenant: every billed credit-report view
    (client, when, access window) plus the full metered-usage summary for the
    selected month."""
    tenant = get_object_or_404(UserProfile.objects.select_related('user'), pk=tenant_id)
    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    summary = usage_summary(tenant, year, month)
    views_qs = (CreditCheckAccess.objects
                .filter(tenant=tenant, accessed_at__year=year, accessed_at__month=month)
                .order_by('-accessed_at'))
    now = timezone.now()
    per_view_price = summary['pricing'].price_per_credit_check
    view_rows = []
    for access in views_qs[:300]:
        client = ClientProfile.objects.filter(
            LUID=tenant.LUID, CUID=access.client_cuid).first() \
            or ClientProfile.objects.filter(CUID=access.client_cuid).first()
        view_rows.append({
            'access': access,
            'client': client,
            'price': per_view_price,
            'active': access.expires_at > now,
        })

    context = {
        'nav': 'sa_billing',
        'tenant': tenant,
        'summary': summary,
        'view_rows': view_rows,
        'views_count': views_qs.count(),
        'year': year,
        'month': month,
        'months': [(m, datetime.date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        'years': list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'saasadmin/tenant_usage.html', context)


@superuser_required
def sa_rating_rules(request):
    """Rating Calculation settings: every action DCC studies when computing
    the benchmark credit score, with editable points, direction
    (increase/reduce), optional cap and an enable switch."""
    rules = RatingRule.as_map()  # seeds any missing rows with defaults

    if request.method == 'POST':
        if request.POST.get('action') == 'reset_defaults':
            RatingRule.objects.all().delete()
            RatingRule.as_map()
            messages.success(request, 'Rating calculation reset to defaults.', extra_tags='info')
            return redirect('sa_rating_rules')

        for rule in rules.values():
            points = request.POST.get(f'points__{rule.action}')
            direction = request.POST.get(f'direction__{rule.action}')
            cap = request.POST.get(f'cap__{rule.action}', '').strip()
            try:
                rule.points = max(int(points), 0)
            except (TypeError, ValueError):
                pass
            if direction in (RatingRule.INCREASE, RatingRule.REDUCE):
                rule.direction = direction
            if cap == '':
                rule.cap = None
            else:
                try:
                    rule.cap = max(int(cap), 0) or None
                except (TypeError, ValueError):
                    pass
            rule.enabled = f'enabled__{rule.action}' in request.POST
            rule.save()
        messages.success(request, 'Rating calculation settings saved. New weights apply from the next recompute (nightly, or on the next paid view).', extra_tags='info')
        return redirect('sa_rating_rules')

    ordered = [rules[a] for a in RatingRule.DEFAULTS if a in rules]
    # any extra rows not in DEFAULTS (future-proofing)
    ordered += [r for a, r in sorted(rules.items()) if a not in RatingRule.DEFAULTS]

    context = {
        'nav': 'sa_rating_rules',
        'rules': ordered,
        'scored_clients': ClientCreditScore.objects.count(),
    }
    return render(request, 'saasadmin/rating_rules.html', context)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

@superuser_required
def sa_invoices(request):
    """Monthly invoices per tenant: generate, send/resend, mark paid — plus
    the auto-send settings (enable/disable, day of month, CC address)."""
    today = datetime.date.today()
    prev = (today.replace(day=1) - datetime.timedelta(days=1))
    try:
        year = int(request.GET.get('year', prev.year))
        month = int(request.GET.get('month', prev.month))
    except (TypeError, ValueError):
        year, month = prev.year, prev.month

    billing = BillingSettings.current()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_settings':
            if billing.pk is None:
                billing = BillingSettings()
            billing.auto_send_enabled = request.POST.get('auto_send_enabled') == 'on'
            try:
                billing.send_day = min(max(int(request.POST.get('send_day', 3)), 1), 28)
            except (TypeError, ValueError):
                pass
            billing.cc_email = (request.POST.get('cc_email') or '').strip()
            billing.save()
            messages.success(request, 'Billing settings saved.', extra_tags='info')

        elif action == 'generate_all':
            count = 0
            for tenant in UserProfile.objects.filter(use_loanmasta=True):
                generate_invoice(tenant, year, month)
                count += 1
            messages.success(request, f'Generated/refreshed {count} invoice(s) for {month:02d}/{year}.', extra_tags='info')

        elif action == 'send':
            invoice = get_object_or_404(Invoice, pk=request.POST.get('invoice_id'))
            try:
                send_invoice(invoice, cc_email=billing.cc_email)
                messages.success(request, f'Invoice {invoice.number} emailed to {invoice.tenant}.', extra_tags='info')
            except Exception as exc:
                messages.error(request, f'Could not send {invoice.number}: {exc}', extra_tags='danger')

        elif action == 'mark_paid':
            invoice = get_object_or_404(Invoice, pk=request.POST.get('invoice_id'))
            invoice.status = 'PAID'
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=['status', 'paid_at'])
            messages.success(request, f'Invoice {invoice.number} marked paid.', extra_tags='info')

        return redirect(f"{request.path}?year={year}&month={month}")

    invoices = Invoice.objects.filter(year=year, month=month).select_related('tenant')
    total = invoices.aggregate(s=Sum('total'))['s'] or 0

    context = {
        'nav': 'sa_invoices',
        'invoices': invoices,
        'total': total,
        'billing': billing,
        'year': year,
        'month': month,
        'months': [(m, datetime.date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        'years': list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'saasadmin/invoices.html', context)


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------

@superuser_required
def sa_identity(request):
    """Queue of profile clusters that may be the same person. The scan button
    refreshes the queue from the whole database."""
    if request.method == 'POST' and request.POST.get('action') == 'scan':
        result = scan_identity_cases()
        messages.success(
            request,
            f"Scan complete: {result['auto']} linked cluster(s) and {result['review']} ambiguous group(s) queued.",
            extra_tags='info')
        return redirect('sa_identity')

    status = request.GET.get('status', 'PENDING')
    cases = IdentityCase.objects.all()
    if status != 'ALL':
        cases = cases.filter(status=status)

    rows = []
    for case in cases[:200]:
        rows.append({'case': case, 'count': len(case.member_ids)})

    context = {
        'nav': 'sa_identity',
        'rows': rows,
        'status': status,
        'pending_count': IdentityCase.objects.filter(status='PENDING').count(),
        'statuses': IdentityCase.STATUS_CHOICES,
    }
    return render(request, 'saasadmin/identity_list.html', context)


@superuser_required
def sa_identity_case(request, case_id):
    """Side-by-side review of one cluster with the three resolution actions:
    MERGE (keep one profile), LINK (same person, keep per-tenant profiles) or
    DISMISS (different people — the matcher never merges them again)."""
    case = get_object_or_404(IdentityCase, pk=case_id)
    members = case.members()

    if request.method == 'POST' and case.status == 'PENDING':
        action = request.POST.get('action')
        who = request.user.email

        if action == 'merge':
            primary_id = request.POST.get('primary_id')
            primary = next((p for p in members if str(p.pk) == str(primary_id)), None)
            if primary is None:
                messages.error(request, 'Select which profile to keep.', extra_tags='danger')
                return redirect('sa_identity_case', case_id=case.pk)
            duplicates = [p for p in members if p.pk != primary.pk]
            merge_profiles(primary, duplicates, by=who)
            case.status = 'MERGED'
            case.primary = primary
            messages.success(request, f'Merged {len(duplicates)} duplicate profile(s) into {primary}.', extra_tags='info')

        elif action == 'link':
            primary_id = request.POST.get('primary_id')
            case.primary = next((p for p in members if str(p.pk) == str(primary_id)), None)
            case.status = 'LINKED'
            # make sure the person's single rating is (re)computed now
            seed = members[0]
            ClientCreditScore.ensure(case.primary or seed,
                                     profiles=matched_profiles(ClientProfile.objects.filter(pk=seed.pk)))
            messages.success(request, 'Confirmed as the same person — profiles stay per tenant, one shared rating.', extra_tags='info')

        elif action == 'dismiss':
            IdentityExclusion.separate(members, by=who)
            case.status = 'DISMISSED'
            messages.success(request, 'Recorded as different people — these profiles will never be auto-merged.', extra_tags='info')

        else:
            messages.error(request, 'Unknown action.', extra_tags='danger')
            return redirect('sa_identity_case', case_id=case.pk)

        case.resolved_at = timezone.now()
        case.resolved_by = who
        case.note = (request.POST.get('note') or '')[:255]
        case.save()
        return redirect('sa_identity')

    from loan.models import Loan
    member_rows = []
    for p in members:
        member_rows.append({
            'profile': p,
            'tenant': p.user_profile,
            'loans': Loan.objects.filter(Q(owner=p) | Q(LUID=p.LUID, UID=p.CUID)).distinct().count() if p.CUID else Loan.objects.filter(owner=p).count(),
            'history': p.history.count(),
            'employers': p.client_employer.count(),
            'banks': p.client_bankaccount.count(),
            'uploads': p.client_uploads.count(),
        })

    luids = {p.LUID for p in members if p.LUID}
    context = {
        'nav': 'sa_identity',
        'case': case,
        'member_rows': member_rows,
        'cross_tenant': len(luids) > 1,
    }
    return render(request, 'saasadmin/identity_case.html', context)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@superuser_required
def sa_users(request):
    query = request.GET.get('q', '').strip()
    users = User.objects.select_related('userprofile').order_by('-date_joined')
    if query:
        users = users.filter(
            Q(email__icontains=query) |
            Q(username__icontains=query) |
            Q(userprofile__organisation__icontains=query) |
            Q(userprofile__first_name__icontains=query) |
            Q(userprofile__last_name__icontains=query)
        )
    context = {
        'nav': 'sa_users',
        'users': users,
        'query': query,
    }
    return render(request, 'saasadmin/users.html', context)


@superuser_required
@require_POST
def sa_user_toggle_active(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.active = not user.active
    user.save()
    state = 'activated' if user.active else 'deactivated'
    messages.success(request, f'User {user.email} {state}.', extra_tags='info')
    return redirect('sa_users')


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@superuser_required
def sa_clients(request):
    query = request.GET.get('q', '').strip()
    tenant_filter = request.GET.get('tenant', '').strip()

    clients = ClientProfile.objects.select_related('user_profile').order_by('-updated_at')
    if query:
        clients = clients.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(CUID__icontains=query) |
            Q(LUID__icontains=query) |
            Q(nid_number__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(email__icontains=query) |
            Q(user_profile__organisation__icontains=query)
        )
    if tenant_filter:
        clients = clients.filter(user_profile_id=tenant_filter)

    tenants = UserProfile.objects.filter(use_loanmasta=True).order_by('organisation')
    context = {
        'nav': 'sa_clients',
        'clients': clients,
        'query': query,
        'tenant_filter': tenant_filter,
        'tenants': tenants,
    }
    return render(request, 'saasadmin/clients.html', context)


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------

@superuser_required
def sa_loans(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    tenant_filter = request.GET.get('tenant', '').strip()

    loans = Loan.objects.select_related('owner', 'lender').order_by('-created_at')
    if query:
        loans = loans.filter(
            Q(owner__first_name__icontains=query) |
            Q(owner__last_name__icontains=query) |
            Q(owner__CUID__icontains=query) |
            Q(lender__organisation__icontains=query)
        )
    if status_filter:
        loans = loans.filter(status=status_filter)
    if tenant_filter:
        loans = loans.filter(lender_id=tenant_filter)

    agg = loans.aggregate(
        total_amount=Sum('amount'),
        total_outstanding=Sum('total_outstanding'),
        total_arrears=Sum('total_arrears'),
    )

    tenants = UserProfile.objects.filter(use_loanmasta=True).order_by('organisation')
    status_choices = [c[0] for c in Loan._meta.get_field('status').choices or []]

    context = {
        'nav': 'sa_loans',
        'loans': loans[:500],
        'total_count': loans.count(),
        'agg': agg,
        'query': query,
        'status_filter': status_filter,
        'tenant_filter': tenant_filter,
        'tenants': tenants,
        'status_choices': ['RUNNING', 'DEFAULTED', 'COMPLETED', 'UNDER REVIEW', 'APPROVED', 'REJECTED', 'ON HOLD'],
    }
    return render(request, 'saasadmin/loans.html', context)


# ---------------------------------------------------------------------------
# DCC Report
# ---------------------------------------------------------------------------

@superuser_required
def sa_dcc_report(request):
    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    pricing = PricingSettings.current()
    logs = ApiUsageLog.objects.filter(created_at__year=year, created_at__month=month)

    tenant_rows = []
    grand_total_cost = decimal.Decimal('0.00')
    grand_total_checks = 0
    for tenant in UserProfile.objects.filter(use_loanmasta=True).order_by('organisation'):
        tl = logs.filter(tenant=tenant)
        checks = tl.filter(action='CREDIT_CHECK').aggregate(n=Sum('units'))['n'] or 0
        cost = pricing.monthly_base_fee + ApiUsageLog.cost_for('CREDIT_CHECK', checks, pricing)
        grand_total_cost += cost
        grand_total_checks += checks
        tenant_rows.append({
            'tenant': tenant,
            'checks': checks,
            'cost': cost,
            'enabled': tenant.credit_check_enabled,
        })

    grade_dist = ClientCreditScore.objects.values('grade').annotate(count=Count('id')).order_by('grade')
    avg_score = ClientCreditScore.objects.aggregate(avg=Avg('score'))['avg'] or 0

    top_accesses = (
        CreditCheckAccess.objects
        .filter(accessed_at__year=year, accessed_at__month=month)
        .values('client_cuid')
        .annotate(access_count=Count('id'))
        .order_by('-access_count')[:10]
    )
    top_clients = []
    for row in top_accesses:
        cp = ClientProfile.objects.filter(CUID=row['client_cuid']).first()
        if cp:
            top_clients.append({'client': cp, 'access_count': row['access_count']})

    context = {
        'nav': 'sa_dcc_report',
        'tenant_rows': tenant_rows,
        'grand_total_cost': grand_total_cost,
        'grand_total_checks': grand_total_checks,
        'pricing': pricing,
        'grade_dist': list(grade_dist),
        'avg_score': round(avg_score),
        'top_clients': top_clients,
        'year': year,
        'month': month,
        'months': [(m, datetime.date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        'years': list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'saasadmin/dcc_report.html', context)


# ---------------------------------------------------------------------------
# Platform settings
# ---------------------------------------------------------------------------

@superuser_required
def sa_settings(request):
    platform = PlatformSettings.current()
    pricing  = PricingSettings.current()

    if request.method == 'POST':
        if platform.pk is None:
            platform = PlatformSettings()
        platform.borrower_portal_enabled      = request.POST.get('borrower_portal_enabled') == 'on'
        platform.require_consent_before_share  = request.POST.get('require_consent_before_share') == 'on'
        platform.alert_on_status_change        = request.POST.get('alert_on_status_change') == 'on'
        platform.alert_on_new_view             = request.POST.get('alert_on_new_view') == 'on'
        try:
            platform.default_expiry_years = max(1, int(request.POST.get('default_expiry_years', 7)))
        except (ValueError, TypeError):
            pass
        platform.save()
        messages.success(request, 'Platform settings saved.', extra_tags='info')
        return redirect('sa_settings')

    context = {
        'nav':      'sa_settings',
        'platform': platform,
        'pricing':  pricing,
    }
    return render(request, 'saasadmin/settings.html', context)


# ---------------------------------------------------------------------------
# Third-party API key management
# ---------------------------------------------------------------------------

@superuser_required
def sa_tp_api_keys(request):
    from thirdparty_api.models import ThirdPartyApiKey
    keys    = ThirdPartyApiKey.objects.order_by('-created_at')
    new_key = request.session.pop('new_tp_key_raw', None)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name    = request.POST.get('name', '').strip()
            email   = request.POST.get('contact_email', '').strip()
            perms   = request.POST.getlist('permissions')
            limit   = int(request.POST.get('rate_limit_per_day', 1000) or 1000)
            _, raw  = ThirdPartyApiKey.generate(name=name, contact_email=email, permissions=perms)
            ThirdPartyApiKey.objects.filter(key_prefix=raw[:10]).update(rate_limit_per_day=limit)
            request.session['new_tp_key_raw'] = raw
            messages.success(request, f'API key for "{name}" created. Copy it now — it will not be shown again.', extra_tags='info')
            return redirect('sa_tp_api_keys')

        elif action == 'toggle':
            from thirdparty_api.models import ThirdPartyApiKey as TpKey
            key = get_object_or_404(TpKey, pk=request.POST.get('key_id'))
            key.is_active = not key.is_active
            key.save(update_fields=['is_active'])
            messages.success(request, f'Key {key.key_prefix}… {"enabled" if key.is_active else "disabled"}.', extra_tags='info')
            return redirect('sa_tp_api_keys')

        elif action == 'delete':
            from thirdparty_api.models import ThirdPartyApiKey as TpKey
            key = get_object_or_404(TpKey, pk=request.POST.get('key_id'))
            key.delete()
            messages.success(request, 'API key deleted.', extra_tags='info')
            return redirect('sa_tp_api_keys')

    from thirdparty_api.models import ThirdPartyApiKey
    return render(request, 'saasadmin/tp_api_keys.html', {
        'nav':      'sa_settings',
        'keys':     ThirdPartyApiKey.objects.order_by('-created_at'),
        'new_key':  new_key,
        'perm_choices': ThirdPartyApiKey.PERMISSIONS_CHOICES,
    })


# ---------------------------------------------------------------------------
# Default notice & dispute admin
# ---------------------------------------------------------------------------

@superuser_required
def sa_default_notices(request):
    from client.models import DefaultNotice
    status_filter = request.GET.get('status', '')
    notices = DefaultNotice.objects.select_related('client', 'tenant').order_by('-created_at')
    if status_filter:
        notices = notices.filter(status=status_filter)

    if request.method == 'POST':
        action    = request.POST.get('action')
        notice_id = request.POST.get('notice_id')
        notice    = get_object_or_404(DefaultNotice, pk=notice_id)

        if action == 'notify':
            from datetime import timedelta
            notice.status               = 'NOTIFIED'
            notice.borrower_notified_at = timezone.now()
            notice.notification_method  = 'EMAIL'
            notice.grace_expires_at     = timezone.now() + timedelta(days=notice.grace_days)
            notice.save(update_fields=['status', 'borrower_notified_at', 'notification_method', 'grace_expires_at'])
            # Send email to borrower
            _sa_send_default_notice_email(notice)
            messages.success(request, f'Borrower notified. Grace period expires {notice.grace_expires_at:%Y-%m-%d}.', extra_tags='info')

        elif action == 'list':
            notice.status    = 'LISTED'
            notice.listed_at = timezone.now()
            notice.listed_by = request.user.email
            notice.save(update_fields=['status', 'listed_at', 'listed_by'])
            # Update ClientProfile status
            client = notice.client
            client.dcc_status  = 'DEFAULT'
            client.dcc_flagged = True
            client.save(update_fields=['dcc_status', 'dcc_flagged'])
            messages.success(request, 'Default listed — ClientProfile updated.', extra_tags='info')

        elif action == 'settle':
            notice.status     = 'SETTLED'
            notice.settled_at = timezone.now()
            notice.save(update_fields=['status', 'settled_at'])
            # Only clear profile if no other active listed notice
            still_active = DefaultNotice.objects.filter(client=notice.client, status='LISTED').exists()
            if not still_active:
                notice.client.dcc_status  = 'SETTLED'
                notice.client.dcc_flagged = False
                notice.client.save(update_fields=['dcc_status', 'dcc_flagged'])
            messages.success(request, 'Default marked settled. ClientProfile updated.', extra_tags='info')

        elif action == 'cancel':
            notice.status = 'CANCELLED'
            notice.save(update_fields=['status'])
            messages.success(request, 'Notice cancelled.', extra_tags='info')

        return redirect(f'{request.path}?status={status_filter}')

    return render(request, 'saasadmin/default_notices.html', {
        'nav':           'sa_clients',
        'notices':       notices,
        'status_filter': status_filter,
        'status_choices': DefaultNotice.STATES,
    })


def _sa_send_default_notice_email(notice):
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail
    client = notice.client
    recipients = [e for e in [client.email] if e]
    if not recipients:
        return
    body = (
        f'Dear {client.first_name} {client.last_name},\n\n'
        f'A credit default notice has been submitted against your record by {notice.tenant}.\n\n'
        f'Amount: K {notice.amount_owed:.2f}\n'
        f'Reason: {notice.reason}\n\n'
        f'You have {notice.grace_days} days from today to resolve this matter before it '
        f'is formally listed on your DCC credit file. Grace period expires: '
        f'{notice.grace_expires_at:%Y-%m-%d %H:%M} (POM time).\n\n'
        f'To dispute this notice or for assistance, contact DCC.\n\nDCC — Dinau Control Center'
    )
    send_mail(
        subject='DCC — Credit Default Notice',
        message=body,
        from_email=dj_settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=True,
    )


@superuser_required
def sa_disputes(request):
    from client.models import Dispute
    status_filter = request.GET.get('status', '')
    disputes = Dispute.objects.select_related('client', 'filed_by_tenant').order_by('-created_at')
    if status_filter:
        disputes = disputes.filter(status=status_filter)

    if request.method == 'POST':
        action     = request.POST.get('action')
        dispute_id = request.POST.get('dispute_id')
        dispute    = get_object_or_404(Dispute, pk=dispute_id)

        if action in ('resolve', 'dismiss'):
            dispute.status      = 'RESOLVED' if action == 'resolve' else 'DISMISSED'
            dispute.resolution  = request.POST.get('resolution', '').strip()
            dispute.resolved_by = request.user.email
            dispute.resolved_at = timezone.now()
            dispute.save(update_fields=['status', 'resolution', 'resolved_by', 'resolved_at'])
            messages.success(request, f'Dispute #{dispute.pk} {dispute.status}.', extra_tags='info')
        elif action == 'under_review':
            dispute.status = 'UNDER_REVIEW'
            dispute.save(update_fields=['status'])
            messages.success(request, f'Dispute #{dispute.pk} marked Under Review.', extra_tags='info')

        return redirect(f'{request.path}?status={status_filter}')

    return render(request, 'saasadmin/disputes.html', {
        'nav':           'sa_clients',
        'disputes':      disputes,
        'status_filter': status_filter,
        'status_choices': Dispute.STATUS_CHOICES,
    })
