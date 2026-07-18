from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from client.models import ClientCreditScore, ClientProfile, matched_profiles
from loan.models import Loan
from transaction.models import Transaction

from .models import CreditCheckAccess, PricingSettings, log_usage, usage_summary
from .permissions import TenantAPIKey
from .serializers import ClientProfileSerializer, LoanSerializer, TransactionSerializer

# All endpoints require the tenant machine-to-machine headers
# (X-API-KEY + X-TENANT-LUID, see api/permissions.py). The authenticated
# tenant is available as request.tenant and every billable call is metered.
#
# Credit reports are PAY-PER-VIEW:
#   GET  credit_check/<uid>/          free — returns a locked stub unless the
#                                     tenant holds a valid paid access window
#   POST credit_check/<uid>/unlock/   the billable "View Data" trigger — opens
#                                     an access window (tenant's configured
#                                     hours, default 12) and returns the report
#   GET  credit_rating/<uid>/         benchmark score only (billed per lookup),
#                                     for tenant auto credit-check decisions
#   GET  billing_summary/             tenant's own month-to-date usage & cost


def _match(tenant, uid):
    """All ClientProfile rows for the person behind this tenant's client uid.

    Seeds with the tenant's own copy (LUID+CUID) and falls back to any
    tenant's copy with that CUID, then expands across tenants on identity
    (NID / passport / licence / name+DOB)."""
    seed = ClientProfile.objects.filter(LUID=tenant.LUID, CUID=uid)
    if not seed.exists():
        seed = ClientProfile.objects.filter(CUID=uid)
    return matched_profiles(seed)


def _primary(tenant, profiles):
    """The tenant's own copy when it has one, else the freshest profile."""
    for p in profiles:
        if p.LUID == tenant.LUID:
            return p
    return sorted(profiles, key=lambda p: p.updated_at or p.created_at, reverse=True)[0]


def _valid_access(tenant, uid):
    return (CreditCheckAccess.objects
            .filter(tenant=tenant, client_cuid=str(uid), expires_at__gt=timezone.now())
            .order_by('-expires_at').first())


def _access_info(tenant, access):
    pricing = PricingSettings.current()
    info = {
        'unlocked': access is not None,
        'window_hours': tenant.credit_check_window_hours,
        'price_per_view': pricing.price_per_credit_check,
        'currency': pricing.currency,
    }
    if access is not None:
        info['accessed_at'] = access.accessed_at
        info['expires_at'] = access.expires_at
    return info


def _full_payload(tenant, uid, profiles, access):
    """The consolidated credit report across every matched profile. Loan and
    transaction detail is still gated by the tenant's DCC plan flags."""
    primary = _primary(tenant, profiles)
    score = ClientCreditScore.ensure(primary, profiles=profiles)

    loan_q = Q(owner__in=profiles)
    txn_q = Q(owner__in=profiles)
    for p in profiles:
        if p.CUID:
            loan_q |= Q(LUID=p.LUID, UID=p.CUID)
            txn_q |= Q(luid=p.LUID, uid=p.CUID)
    loans = Loan.objects.filter(loan_q).distinct()
    transactions = Transaction.objects.filter(txn_q).distinct().order_by('-date')[:50]

    return {
        'found': True,
        'locked': False,
        'plan': tenant.plan,
        'access': _access_info(tenant, access),
        'client': ClientProfileSerializer(primary).data,
        'summary': {
            'score': score.score,
            'grade': score.grade,
            'credit_rating': primary.credit_rating,
            'tenants_reporting': score.tenants_reporting,
            'identity_changes': score.identity_changes,
            'status_events': score.status_events,
            'months_active': score.months_active,
            'total_loans': score.total_loans,
            'running_loans': loans.filter(status='RUNNING').count(),
            'completed_loans': score.completed_loans,
            'defaulted_loans': score.defaulted_loans,
            'recovery_loans': score.recovery_loans,
            'total_outstanding': score.total_outstanding or Decimal('0.00'),
            'total_arrears': loans.aggregate(a=Sum('total_arrears'))['a'] or Decimal('0.00'),
            'dcc_flagged': any(p.dcc_flagged for p in profiles),
            'dcc_status': primary.dcc_status,
        },
        'loans': (LoanSerializer(loans, many=True).data
                  if tenant.can_view_loans else None),
        'transactions': (TransactionSerializer(transactions, many=True).data
                         if tenant.can_view_transactions else None),
    }


@api_view(['GET'])
@permission_classes([TenantAPIKey])
def get_clientprofile(request, uid):
    client = get_object_or_404(ClientProfile, CUID=uid)
    serializer = ClientProfileSerializer(client)
    log_usage(request.tenant, 'PROFILE_LOOKUP', detail=uid)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([TenantAPIKey])
def get_client_loans(request, uid):
    if not request.tenant.can_view_loans:
        return Response({'detail': 'Loan visibility is not included in your DCC plan.'},
                        status=status.HTTP_403_FORBIDDEN)
    loans = Loan.objects.filter(Q(UID=uid) | Q(owner__CUID=uid)).distinct()
    serializer = LoanSerializer(loans, many=True, context={'request': request})
    log_usage(request.tenant, 'LOANS_LOOKUP', detail=uid)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([TenantAPIKey])
def get_client_transactions(request, uid):
    if not request.tenant.can_view_transactions:
        return Response({'detail': 'Transaction visibility is not included in your DCC plan.'},
                        status=status.HTTP_403_FORBIDDEN)
    transactions = Transaction.objects.filter(Q(uid=uid) | Q(owner__CUID=uid)).distinct()
    serializer = TransactionSerializer(transactions, many=True, context={'request': request})
    log_usage(request.tenant, 'TRANSACTIONS_LOOKUP', detail=uid)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([TenantAPIKey])
def credit_check(request, uid):
    """Credit report status/content for one client — never billed by itself.

    If the tenant holds a valid paid access window for this client the full
    report is returned; otherwise a locked stub (enough to render the
    'View Data' overlay: match found, name, window hours, price)."""
    if not request.tenant.credit_check_enabled:
        return Response({'detail': 'Credit checks are not enabled for your DCC account.'},
                        status=status.HTTP_403_FORBIDDEN)

    profiles = _match(request.tenant, uid)
    if not profiles:
        return Response(
            {'found': False, 'detail': 'Client is not in DCC Credit Database.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    access = _valid_access(request.tenant, uid)
    if access is None:
        primary = _primary(request.tenant, profiles)
        return Response({
            'found': True,
            'locked': True,
            'plan': request.tenant.plan,
            'access': _access_info(request.tenant, None),
            'client': {
                'CUID': primary.CUID,
                'first_name': primary.first_name,
                'last_name': primary.last_name,
            },
        })

    return Response(_full_payload(request.tenant, uid, profiles, access))


@api_view(['POST'])
@permission_classes([TenantAPIKey])
def credit_check_unlock(request, uid):
    """The pay-per-view trigger behind the tenant's 'View Data' button.

    Opens (and bills) a fresh access window for this tenant+client — valid for
    the tenant's configured hours (default 12) — then returns the full report.
    Idempotent while a window is still open: no double billing."""
    if not request.tenant.credit_check_enabled:
        return Response({'detail': 'Credit checks are not enabled for your DCC account.'},
                        status=status.HTTP_403_FORBIDDEN)

    profiles = _match(request.tenant, uid)
    if not profiles:
        return Response(
            {'found': False, 'detail': 'Client is not in DCC Credit Database.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    access = _valid_access(request.tenant, uid)
    charged = Decimal('0.00')
    if access is None:
        hours = request.tenant.credit_check_window_hours or 12
        access = CreditCheckAccess.objects.create(
            tenant=request.tenant,
            client_cuid=str(uid),
            expires_at=timezone.now() + timedelta(hours=hours),
        )
        log_usage(request.tenant, 'CREDIT_CHECK', detail=uid)
        charged = PricingSettings.current().price_per_credit_check

    payload = _full_payload(request.tenant, uid, profiles, access)
    payload['charged'] = charged
    return Response(payload)


@api_view(['GET'])
@permission_classes([TenantAPIKey])
def credit_rating(request, uid):
    """Benchmark score only — the single number tenants feed into their
    automatic credit-check rules (registration / application / limit
    decisions). Billed per lookup at the rating-check price."""
    profiles = _match(request.tenant, uid)
    if not profiles:
        return Response(
            {'found': False, 'detail': 'Client is not in DCC Credit Database.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    primary = _primary(request.tenant, profiles)
    score = ClientCreditScore.ensure(primary, profiles=profiles)
    log_usage(request.tenant, 'RATING_CHECK', detail=uid)
    return Response({
        'found': True,
        'score': score.score,
        'grade': score.grade,
        'credit_rating': primary.credit_rating,
        'dcc_flagged': any(p.dcc_flagged for p in profiles),
        'dcc_status': primary.dcc_status,
        'computed_at': score.computed_at,
    })


@api_view(['GET'])
@permission_classes([TenantAPIKey])
def billing_summary(request):
    """This tenant's month-to-date DCC usage and cost (free to call). Used by
    the tenant LMS to show the running cost total on its admin dashboard and
    in its DCC report. Optional ?year=&month= for past months."""
    now = timezone.now()
    try:
        year = int(request.GET.get('year', now.year))
        month = int(request.GET.get('month', now.month))
    except (TypeError, ValueError):
        year, month = now.year, now.month

    summary = usage_summary(request.tenant, year, month)
    views = (CreditCheckAccess.objects
             .filter(tenant=request.tenant, accessed_at__year=year, accessed_at__month=month)
             .order_by('-accessed_at'))
    return Response({
        'currency': summary['currency'],
        'year': year,
        'month': month,
        'base_fee': summary['base_fee'],
        'rows': [{'action': r['action'], 'label': r['label'], 'units': r['units'],
                  'unit_price': r['unit_price'], 'cost': r['cost']} for r in summary['rows']],
        'total': summary['total'],
        'paid_views': views.count(),
        'recent_views': [
            {'client_cuid': v.client_cuid, 'accessed_at': v.accessed_at, 'expires_at': v.expires_at}
            for v in views[:20]
        ],
    })
