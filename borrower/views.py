from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from api.models import PlatformSettings
from client.models import ClientConsent, ClientProfile, Dispute, EnquiryLog


# ── portal gate ─────────────────────────────────────────────────────────────

def _portal_enabled():
    return PlatformSettings.current().borrower_portal_enabled


def _borrower_required(view_fn):
    def wrapper(request, *args, **kwargs):
        if not _portal_enabled():
            return render(request, 'borrower/portal_disabled.html', {}, status=503)
        if not request.session.get('borrower_account_id'):
            return redirect('borrower_login')
        return view_fn(request, *args, **kwargs)
    wrapper.__name__ = view_fn.__name__
    return wrapper


def _get_account(request):
    from borrower.models import BorrowerAccount
    return BorrowerAccount.objects.select_related('client').get(pk=request.session['borrower_account_id'])


# ── login / logout ───────────────────────────────────────────────────────────

def borrower_login(request):
    if not _portal_enabled():
        return render(request, 'borrower/portal_disabled.html', {}, status=503)

    if request.method == 'POST':
        from borrower.models import BorrowerAccount
        email = request.POST.get('email', '').strip().lower()
        pin   = request.POST.get('pin', '').strip()

        try:
            client = ClientProfile.objects.get(email__iexact=email)
        except ClientProfile.DoesNotExist:
            messages.error(request, 'No account found with that email.')
            return render(request, 'borrower/login.html')

        try:
            account = client.borrower_account
        except BorrowerAccount.DoesNotExist:
            messages.error(request, 'No portal account exists for this email. Contact DCC to register.')
            return render(request, 'borrower/login.html')

        if not account.is_active:
            messages.error(request, 'Your portal account is suspended.')
            return render(request, 'borrower/login.html')

        if not account.check_pin(pin):
            messages.error(request, 'Incorrect PIN.')
            return render(request, 'borrower/login.html')

        account.last_login = timezone.now()
        account.save(update_fields=['last_login'])
        request.session['borrower_account_id'] = account.pk
        return redirect('borrower_dashboard')

    return render(request, 'borrower/login.html')


@require_POST
def borrower_logout(request):
    request.session.pop('borrower_account_id', None)
    return redirect('borrower_login')


# ── dashboard (own credit summary) ──────────────────────────────────────────

@_borrower_required
def borrower_dashboard(request):
    account = _get_account(request)
    client  = account.client

    score = getattr(client, 'credit_score', None)
    loans = list(client.loan_owner.order_by('-funding_date')[:10]) if hasattr(client, 'loan_owner') else []
    enquiries = EnquiryLog.objects.filter(client=client)[:10]
    open_disputes = Dispute.objects.filter(client=client, status='OPEN').count()

    return render(request, 'borrower/dashboard.html', {
        'client':        client,
        'score':         score,
        'loans':         loans,
        'enquiries':     enquiries,
        'open_disputes': open_disputes,
    })


# ── enquiry log (who viewed my file) ────────────────────────────────────────

@_borrower_required
def borrower_enquiries(request):
    account   = _get_account(request)
    enquiries = EnquiryLog.objects.filter(client=account.client)[:200]
    return render(request, 'borrower/enquiries.html', {'enquiries': enquiries})


# ── disputes ────────────────────────────────────────────────────────────────

@_borrower_required
def borrower_disputes(request):
    account  = _get_account(request)
    client   = account.client
    disputes = Dispute.objects.filter(client=client)

    if request.method == 'POST':
        dtype = request.POST.get('dispute_type', 'OTHER')
        field = request.POST.get('field_disputed', '').strip()
        desc  = request.POST.get('description', '').strip()
        doc   = request.FILES.get('supporting_doc')

        if not desc:
            messages.error(request, 'Please describe the issue.')
        else:
            Dispute.objects.create(
                client=client,
                borrower_email=client.email or '',
                dispute_type=dtype,
                field_disputed=field,
                description=desc,
                supporting_doc=doc,
            )
            messages.success(request, 'Dispute submitted. DCC will review within 5 business days.')
            return redirect('borrower_disputes')

    return render(request, 'borrower/disputes.html', {
        'disputes':     disputes,
        'type_choices': Dispute.TYPE_CHOICES,
    })


# ── consents ─────────────────────────────────────────────────────────────────

@_borrower_required
def borrower_consents(request):
    account  = _get_account(request)
    consents = ClientConsent.objects.filter(client=account.client).select_related('tenant')
    return render(request, 'borrower/consents.html', {'consents': consents})
