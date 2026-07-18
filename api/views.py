from decimal import Decimal

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status

from client.models import ClientProfile
from loan.models import Loan
from transaction.models import Transaction

from .models import log_usage
from .permissions import TenantAPIKey
from .serializers import ClientProfileSerializer, LoanSerializer, TransactionSerializer

# All endpoints require the tenant machine-to-machine headers
# (X-API-KEY + X-TENANT-LUID, see api/permissions.py). The authenticated
# tenant is available as request.tenant and every call is metered for billing.


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
    """Consolidated credit report for one client, for the tenant's loan-review
    screen: profile flags + all known loans + recent transactions + summary.

    What the caller receives is gated by its DCC plan / per-tenant access
    flags (can_view_loans, can_view_transactions), configured in the DCC
    control panel. The summary (flags, rating, counts, totals) is always
    included — that is the core credit-check product."""
    if not request.tenant.credit_check_enabled:
        return Response({'detail': 'Credit checks are not enabled for your DCC account.'},
                        status=status.HTTP_403_FORBIDDEN)

    client = ClientProfile.objects.filter(CUID=uid).first()
    if client is None:
        return Response(
            {'found': False, 'detail': 'Client is not in DCC Credit Database.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    loans = Loan.objects.filter(Q(UID=uid) | Q(owner=client)).distinct()
    transactions = (
        Transaction.objects.filter(Q(uid=uid) | Q(owner=client))
        .distinct().order_by('-date')[:50]
    )

    running = loans.filter(status='RUNNING')
    defaulted = loans.filter(status='DEFAULTED')
    totals = loans.aggregate(
        outstanding=Sum('total_outstanding'), arrears=Sum('total_arrears')
    )

    log_usage(request.tenant, 'CREDIT_CHECK', detail=uid)
    payload = {
        'found': True,
        'plan': request.tenant.plan,
        'client': ClientProfileSerializer(client).data,
        'summary': {
            'total_loans': loans.count(),
            'running_loans': running.count(),
            'defaulted_loans': defaulted.count(),
            'total_outstanding': totals['outstanding'] or Decimal('0.00'),
            'total_arrears': totals['arrears'] or Decimal('0.00'),
            'dcc_flagged': bool(client.dcc_flagged),
            'dcc_status': client.dcc_status,
            'credit_rating': client.credit_rating,
        },
        'loans': (LoanSerializer(loans, many=True).data
                  if request.tenant.can_view_loans else None),
        'transactions': (TransactionSerializer(transactions, many=True).data
                         if request.tenant.can_view_transactions else None),
    }
    return Response(payload)
