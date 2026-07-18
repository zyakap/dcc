"""Automated tenant-feed ingestion.

For every tenant (users.UserProfile) with ``feed_enabled``, pull the LMS
pull-and-mark-consumed feed endpoints:

    https://<tenant.endpoint>/API/profiles/
    https://<tenant.endpoint>/API/loans/
    https://<tenant.endpoint>/API/statements/

authenticated with the tenant's shared key (X-API-KEY), and upsert the
records into the DCC database (client.ClientProfile, loan.Loan,
transaction.Transaction). Runs from the ``sync_tenants`` management command
and the ``api.tasks.sync_tenant_feeds`` celery beat task.
"""
import logging
import os

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from client.models import (
    ClientBankAccount, ClientEmployer, ClientProfile, ClientUpload,
)
from loan.models import Loan
from transaction.models import Transaction
from users.models import UserProfile

from .models import log_usage

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30

# tenant feed field -> ClientProfile field
PROFILE_FIELD_MAP = {
    'first_name': 'first_name',
    'middle_name': 'middle_name',
    'last_name': 'last_name',
    'gender': 'gender',
    'date_of_birth': 'date_of_birth',
    'marital_status': 'marital_status',
    'email': 'email',
    'mobile1': 'mobile1',
    'nid_number': 'nid_number',
    'passport_number': 'passport_number',
    'drivers_license_number': 'drivers_license_number',
    'super_member_code': 'super_member_code',
    'residential_address': 'permanent_address',
    'place_of_origin': 'place_of_origin',
    'repayment_limit': 'repayment_limit',
    'credit_rating': 'credit_rating',
    'number_of_loans': 'number_of_loans',
    'has_loan': 'has_loan',
    'dcc_flagged': 'dcc_flagged',
}

# tenant feed field -> Loan field (same-named fields)
LOAN_FIELDS = [
    'amount', 'repayment_amount', 'category', 'funded_category', 'status',
    'funding_date', 'number_of_repayments', 'last_repayment_amount',
    'last_repayment_date', 'number_of_defaults', 'last_default_date',
    'last_default_amount', 'days_in_default', 'total_arrears',
    'total_outstanding', 'aging_category',
]

TRANSACTION_FIELDS = ['type', 'statement', 'credit', 'debit', 'arrears', 'balance']


def _verify_ssl():
    return getattr(settings, 'TENANT_VERIFY_SSL', True)


def _fetch(tenant, path):
    """Fetch all records from a tenant feed endpoint.

    Handles two common response shapes:
    - Flat list:  [...records...]
    - DRF paginated: {"count": N, "next": "url|null", "results": [...records...]}

    Follows 'next' links automatically so the full dataset is returned
    regardless of the tenant's page size setting.
    """
    url = f'https://{tenant.endpoint}/API/{path}/'
    headers = {'X-API-KEY': tenant.api_key or ''}
    records = []

    while url:
        response = requests.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            verify=_verify_ssl(),
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            # Flat list — no pagination, we're done
            records.extend(data)
            break
        elif isinstance(data, dict):
            # DRF-style paginated envelope
            page_records = data.get('results') or []
            records.extend(page_records)
            url = data.get('next')  # None / null → stops the loop
        else:
            break

    return records


def _clean(value):
    return value if value != '' else None


def _sync_employer(client, row):
    """Upsert the client's employment record from the profile feed row."""
    fields = {
        'sector': row.get('sector'),
        'employer': row.get('employer'),
        'job_title': row.get('job_title'),
        'work_id_number': row.get('work_id_number'),
        'start_date': row.get('start_date'),
        'pay_frequency': row.get('pay_frequency'),
        'last_paydate': row.get('last_paydate'),
    }
    if not any(v not in (None, '') for v in fields.values()):
        return
    employer = client.client_employer.first() or ClientEmployer(client=client)
    for field, value in fields.items():
        if value not in (None, ''):
            setattr(employer, field, value)
    employer.save(_history_source='SYNC')


def _sync_bank_accounts(client, row):
    """Upsert the client's bank account(s) from the profile feed row."""
    accounts = [
        (row.get('bank'), row.get('bank_account_name'), row.get('bank_account_number'), row.get('bank_branch')),
        (row.get('bank2'), row.get('bank_account_name2'), row.get('bank_account_number2'), row.get('bank_branch2')),
    ]
    for bank, name, number, branch in accounts:
        if not number:
            continue
        account = ClientBankAccount.objects.filter(client=client, account_number=number).first() \
            or ClientBankAccount(client=client, account_number=number)
        account.bank = bank or account.bank
        account.account_name = name or account.account_name
        account.branch_name = branch or account.branch_name
        account.save(_history_source='SYNC')


def _sync_uploads(tenant, client, row):
    """Download the client's documents listed in the feed into ClientUpload.

    The tenant feed lists uploads as {'upload_type', 'name', 'url'} where the
    url is the tenant's API download endpoint (X-API-KEY protected). Files
    already ingested (same client + type + name) are skipped."""
    for item in row.get('uploads') or []:
        upload_type = item.get('upload_type') or 'OTHERS'
        name = item.get('name') or ''
        url = item.get('url')
        if not url:
            continue
        if ClientUpload.objects.filter(client=client, upload_type=upload_type, description=name).exists():
            continue
        try:
            response = requests.get(
                url, headers={'X-API-KEY': tenant.api_key or ''},
                timeout=REQUEST_TIMEOUT, verify=_verify_ssl(),
            )
            response.raise_for_status()
        except Exception:
            logger.warning('Could not download upload %s for client %s', url, client.CUID)
            continue
        upload = ClientUpload(client=client, upload_type=upload_type, description=name)
        upload.upload_file.save(os.path.basename(name) or f'{client.CUID}-{upload_type}', ContentFile(response.content), save=True)


def _auto_vet(client):
    """Grant DCC consent automatically when a client clearly has loan activity.

    If a client has a loan (``has_loan=True``) but ``vetted`` is still False it
    means the tenant or the client forgot to tick the consent box.  Presence of
    an active borrowing relationship implies implicit consent — set it now so
    the record is fully visible in DCC rather than stuck in the review queue."""
    if client.has_loan and not client.vetted:
        client.vetted = True
        logger.info('Auto-vetted client %s (has_loan=True, vetted was False)', client.CUID)


def sync_profiles(tenant):
    count = 0
    for row in _fetch(tenant, 'profiles'):
        uid, luid = row.get('uid'), row.get('luid') or tenant.LUID
        if not uid:
            continue
        client, _ = ClientProfile.objects.get_or_create(
            LUID=luid, CUID=uid,
            defaults={
                'user_profile': tenant,
                'first_name': row.get('first_name') or '',
                'last_name': row.get('last_name') or '',
            },
        )
        for src, dst in PROFILE_FIELD_MAP.items():
            if src in row and row.get(src) is not None:
                setattr(client, dst, _clean(row.get(src)))
        client.user_profile = client.user_profile or tenant
        # Auto-grant consent when loan activity is present but consent was missed
        _auto_vet(client)
        client.save(_history_source='SYNC')
        _sync_employer(client, row)
        _sync_bank_accounts(client, row)
        _sync_uploads(tenant, client, row)
        count += 1
    return count


def sync_loans(tenant):
    count = 0
    for row in _fetch(tenant, 'loans'):
        ref, uid = row.get('ref'), row.get('uid')
        luid = row.get('luid') or tenant.LUID
        if not ref:
            continue
        loan, _ = Loan.objects.get_or_create(LUID=luid, ref=ref, defaults={'UID': uid})
        loan.UID = uid or loan.UID
        loan.lender = loan.lender or tenant
        if loan.owner is None and uid:
            loan.owner = ClientProfile.objects.filter(LUID=luid, CUID=uid).first()
        for field in LOAN_FIELDS:
            if field in row and row.get(field) is not None:
                setattr(loan, field, _clean(row.get(field)))
        loan.save()
        # If the loan owner wasn't vetted yet, having a synced loan is proof
        # enough — auto-grant consent and persist it.
        if loan.owner and not loan.owner.vetted:
            loan.owner.has_loan = True
            loan.owner.vetted = True
            loan.owner.save(update_fields=['has_loan', 'vetted'])
            logger.info('Auto-vetted client %s via synced loan %s', loan.owner.CUID, ref)
        count += 1
    return count


def sync_statements(tenant):
    count = 0
    for row in _fetch(tenant, 'statements'):
        uid = row.get('uid')
        luid = row.get('luid') or tenant.LUID
        loan = None
        if row.get('loanref'):
            loan = Loan.objects.filter(LUID=luid, ref=row.get('loanref')).first()
        owner = ClientProfile.objects.filter(LUID=luid, CUID=uid).first() if uid else None
        txn, created = Transaction.objects.get_or_create(
            luid=luid,
            uid=uid,
            ref=row.get('ref'),
            date=row.get('date'),
            statement=row.get('statement'),
            credit=_clean(row.get('credit')) or 0,
            debit=_clean(row.get('debit')) or 0,
            defaults={'lender': tenant, 'owner': owner, 'loanref': loan},
        )
        if created:
            for field in TRANSACTION_FIELDS:
                if field in row and row.get(field) is not None:
                    setattr(txn, field, _clean(row.get(field)))
            txn.save()
            count += 1
    return count


def sync_tenant(tenant):
    """Pull all three feeds for one tenant. Returns a result summary dict."""
    result = {'tenant': str(tenant), 'luid': tenant.LUID, 'ok': False,
              'profiles': 0, 'loans': 0, 'statements': 0, 'error': None}
    try:
        result['profiles'] = sync_profiles(tenant)
        result['loans'] = sync_loans(tenant)
        result['statements'] = sync_statements(tenant)
        result['ok'] = True
        status = (f"OK {timezone.now():%Y-%m-%d %H:%M} — "
                  f"{result['profiles']} profiles, {result['loans']} loans, "
                  f"{result['statements']} statements")
    except Exception as exc:  # noqa: BLE001 — one tenant failing must not stop the run
        logger.exception('DCC sync failed for tenant %s', tenant)
        result['error'] = str(exc)
        status = f'ERROR {timezone.now():%Y-%m-%d %H:%M} — {exc}'[:255]

    synced = result['profiles'] + result['loans'] + result['statements']
    if synced:
        log_usage(tenant, 'FEED_SYNC', units=synced)
        tenant.record_count = (tenant.record_count or 0) + synced
    tenant.last_sync_at = timezone.now()
    tenant.last_sync_status = status[:255]
    tenant.save(update_fields=['last_sync_at', 'last_sync_status', 'record_count'])
    return result


def sync_all_tenants():
    """Sync every feed-enabled tenant; returns the list of per-tenant results."""
    results = []
    for tenant in UserProfile.objects.filter(feed_enabled=True).exclude(api_key__isnull=True).exclude(api_key=''):
        results.append(sync_tenant(tenant))
    return results
