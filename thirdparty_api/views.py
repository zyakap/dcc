"""Third-party REST API — completely separate from the Loanmasta /api/ integration.

Auth: Authorization: Bearer tpk_<key>
"""
import functools

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import PlatformSettings
from client.models import ClientConsent, ClientProfile, Dispute, EnquiryLog, matched_profiles
from thirdparty_api.models import ThirdPartyApiKey, TpApiUsageLog


# ── authentication ──────────────────────────────────────────────────────────

def _resolve_key(request):
    """Return (ThirdPartyApiKey, raw_key) or raise ValueError."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer tpk_'):
        raise ValueError('Missing or malformed Authorization header. Use: Bearer tpk_<key>')
    raw = auth[7:]  # strip 'Bearer '
    prefix = raw[:10]
    try:
        key_obj = ThirdPartyApiKey.objects.get(key_prefix=prefix, is_active=True)
    except ThirdPartyApiKey.DoesNotExist:
        raise ValueError('Invalid API key')
    if not key_obj.verify_key(raw):
        raise ValueError('Invalid API key')
    ThirdPartyApiKey.objects.filter(pk=key_obj.pk).update(last_used=timezone.now())
    return key_obj


def tp_auth(perm=None):
    """Decorator factory: authenticate + optional permission gate."""
    def decorator(view_fn):
        @csrf_exempt
        @functools.wraps(view_fn)
        def wrapper(request, *args, **kwargs):
            try:
                key_obj = _resolve_key(request)
            except ValueError as exc:
                return JsonResponse({'error': str(exc)}, status=401)

            if perm and not key_obj.has_permission(perm):
                return JsonResponse({'error': f'This key does not have the "{perm}" permission.'}, status=403)

            request.tp_key = key_obj
            return view_fn(request, *args, **kwargs)
        return wrapper
    return decorator


def _log(key_obj, endpoint, cuid='', status=200):
    try:
        TpApiUsageLog.objects.create(api_key=key_obj, endpoint=endpoint, cuid=cuid, status=status)
    except Exception:
        pass


def _log_enquiry(client, key_obj, query_type='TPAPI_CHECK'):
    try:
        EnquiryLog.objects.create(client=client, tp_key_name=key_obj.name, query_type=query_type)
    except Exception:
        pass


# ── status endpoint ─────────────────────────────────────────────────────────

@tp_auth()
@require_http_methods(['GET'])
def tp_status(request):
    k = request.tp_key
    _log(k, 'status')
    return JsonResponse({
        'status': 'ok',
        'key_name': k.name,
        'permissions': k.permissions,
        'rate_limit_per_day': k.rate_limit_per_day,
        'last_used': k.last_used.isoformat() if k.last_used else None,
    })


# ── credit score ─────────────────────────────────────────────────────────────

@tp_auth(perm='score_only')
@require_http_methods(['GET'])
def tp_credit_score(request, cuid):
    profiles = ClientProfile.objects.filter(CUID=cuid)
    if not profiles.exists():
        _log(request.tp_key, 'credit_score', cuid, 404)
        return JsonResponse({'error': 'Client not found.'}, status=404)

    all_profiles = matched_profiles(profiles)
    primary      = sorted(all_profiles, key=lambda p: p.updated_at or p.created_at, reverse=True)[0]
    score_obj    = getattr(primary, 'credit_score', None)

    _log_enquiry(primary, request.tp_key, 'SCORE_CHECK')
    _log(request.tp_key, 'credit_score', cuid)

    return JsonResponse({
        'cuid':  cuid,
        'name':  f'{primary.first_name} {primary.last_name}',
        'score': score_obj.score if score_obj else None,
        'grade': score_obj.grade if score_obj else None,
        'computed_at': score_obj.computed_at.isoformat() if score_obj else None,
        'dcc_status':  primary.dcc_status,
        'dcc_flagged': primary.dcc_flagged,
    })


# ── full credit report ───────────────────────────────────────────────────────

@tp_auth(perm='credit_report')
@require_http_methods(['GET'])
def tp_credit_report(request, cuid):
    profiles = ClientProfile.objects.filter(CUID=cuid)
    if not profiles.exists():
        _log(request.tp_key, 'credit_report', cuid, 404)
        return JsonResponse({'error': 'Client not found.'}, status=404)

    all_profiles = matched_profiles(profiles)
    primary      = sorted(all_profiles, key=lambda p: p.updated_at or p.created_at, reverse=True)[0]
    score_obj    = getattr(primary, 'credit_score', None)

    # Aggregate loan summary across all matched profiles
    from loan.models import Loan
    from django.db.models import Sum, Q
    loans = Loan.objects.filter(
        Q(owner__in=all_profiles) | Q(LUID=primary.LUID, UID=primary.CUID)
    ).distinct()
    agg = loans.aggregate(
        total_loans=Sum('number_of_repayments'),   # count proxy
        outstanding=Sum('total_outstanding'),
        arrears=Sum('total_arrears'),
    )
    loan_count   = loans.count()
    loan_summary = [
        {
            'ref':         ln.ref,
            'status':      ln.status,
            'amount':      str(ln.amount or 0),
            'outstanding': str(ln.total_outstanding or 0),
            'arrears':     str(ln.total_arrears or 0),
            'lender':      ln.lender.organisation if ln.lender else None,
            'funding_date': str(ln.funding_date) if ln.funding_date else None,
        }
        for ln in loans[:20]
    ]

    disputes = Dispute.objects.filter(client__in=all_profiles).values('dispute_type', 'status', 'created_at')

    _log_enquiry(primary, request.tp_key, 'TPAPI_CHECK')
    _log(request.tp_key, 'credit_report', cuid)

    return JsonResponse({
        'cuid':           cuid,
        'name':           f'{primary.first_name} {primary.last_name}',
        'dcc_status':     primary.dcc_status,
        'dcc_flagged':    primary.dcc_flagged,
        'score':          score_obj.score if score_obj else None,
        'grade':          score_obj.grade if score_obj else None,
        'loan_count':     loan_count,
        'total_outstanding': str(agg['outstanding'] or 0),
        'total_arrears':  str(agg['arrears'] or 0),
        'loans':          loan_summary,
        'open_disputes':  list(disputes),
        'computed_at':    score_obj.computed_at.isoformat() if score_obj else None,
    })


# ── record consent ───────────────────────────────────────────────────────────

@tp_auth(perm='consent_write')
@csrf_exempt
@require_http_methods(['POST'])
def tp_record_consent(request, cuid):
    import json
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'JSON body required.'}, status=400)

    profiles = ClientProfile.objects.filter(CUID=cuid)
    if not profiles.exists():
        return JsonResponse({'error': 'Client not found.'}, status=404)

    client       = profiles.first()
    consent_type = body.get('consent_type', 'CREDIT_CHECK')
    if consent_type not in dict(ClientConsent.CONSENT_TYPES):
        consent_type = 'CREDIT_CHECK'

    # We need a UserProfile to store the tenant; use a sentinel or store in tp_key_name
    # For third-party consent we skip the tenant FK (it's nullable) and record the key name
    consent = ClientConsent.objects.create(
        client=client,
        tenant_id=None,           # not a DCC tenant
        consent_type=consent_type,
        method=body.get('method', 'DIGITAL'),
        reference=body.get('reference', ''),
        notes=f'Recorded via Third-Party API key: {request.tp_key.name}',
    )
    _log(request.tp_key, 'consent_write', cuid)

    return JsonResponse({'ok': True, 'consent_id': consent.pk, 'consented_at': consent.consented_at.isoformat()}, status=201)


# ── enquiry log ──────────────────────────────────────────────────────────────

@tp_auth(perm='enquiry_log')
@require_http_methods(['GET'])
def tp_enquiry_log(request):
    logs = TpApiUsageLog.objects.filter(api_key=request.tp_key)[:200]
    _log(request.tp_key, 'enquiry_log')
    return JsonResponse({
        'count': logs.count(),
        'results': [
            {
                'endpoint':   l.endpoint,
                'cuid':       l.cuid,
                'status':     l.status,
                'queried_at': l.queried_at.isoformat(),
            }
            for l in logs
        ]
    })
