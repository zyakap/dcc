from decimal import Decimal

from django.db import models

from users.models import UserProfile


class PricingSettings(models.Model):
    """DCC service pricing. One row (the latest is used) — editable from the
    control panel so usage cost can be computed per tenant."""
    updated_at = models.DateTimeField(auto_now=True)
    currency = models.CharField(max_length=10, default='PGK')
    monthly_base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text='Flat monthly access fee per tenant.')
    price_per_credit_check = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Charged each time a tenant unlocks (pays to view) a client credit report.')
    price_per_profile_lookup = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Charged for each single profile/loans/transactions lookup.')
    price_per_record_synced = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.0000'), help_text='Charged per record ingested from the tenant feed.')
    price_per_rating_check = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Charged for each rating-only lookup (used by tenant auto credit-check).')

    class Meta:
        verbose_name = 'Pricing settings'
        verbose_name_plural = 'Pricing settings'

    def __str__(self):
        return f'DCC pricing ({self.currency}, updated {self.updated_at:%Y-%m-%d})'

    @classmethod
    def current(cls):
        return cls.objects.order_by('-updated_at').first() or cls()


class ApiUsageLog(models.Model):
    """One row per billable tenant interaction with DCC."""
    ACTION_CHOICES = [
        ('CREDIT_CHECK', 'Credit check'),
        ('PROFILE_LOOKUP', 'Profile lookup'),
        ('LOANS_LOOKUP', 'Loans lookup'),
        ('TRANSACTIONS_LOOKUP', 'Transactions lookup'),
        ('FEED_SYNC', 'Feed records synced'),
        ('RATING_CHECK', 'Rating-only check'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='usage_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    units = models.PositiveIntegerField(default=1, help_text='1 per lookup/check; record count for feed syncs.')
    detail = models.CharField(max_length=255, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text='Price per unit at the time of the event — later pricing changes never alter past bills. Null on legacy rows (billed at current pricing).')

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['action', 'created_at']),
        ]

    def __str__(self):
        return f'{self.tenant} {self.action} x{self.units} @ {self.created_at:%Y-%m-%d %H:%M}'

    @staticmethod
    def cost_for(action, units, pricing):
        if action == 'CREDIT_CHECK':
            return pricing.price_per_credit_check * units
        if action in ('PROFILE_LOOKUP', 'LOANS_LOOKUP', 'TRANSACTIONS_LOOKUP'):
            return pricing.price_per_profile_lookup * units
        if action == 'FEED_SYNC':
            return pricing.price_per_record_synced * units
        if action == 'RATING_CHECK':
            return pricing.price_per_rating_check * units
        return Decimal('0.00')


def usage_summary(tenant, year, month):
    """Month-to-date billing summary for one tenant: one row per action plus
    the base fee and grand total. Shared by the tenant billing page, the
    saasadmin billing screens, invoicing and the tenant-facing
    billing_summary API.

    Rows that carry a unit_price snapshot are billed at that price; legacy
    rows without one fall back to the current pricing table."""
    import datetime as _dt
    from django.db.models import DecimalField, ExpressionWrapper, F, Sum

    period_start = _dt.datetime(year, month, 1, tzinfo=_dt.timezone.utc)
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    period_end = _dt.datetime(next_year, next_month, 1, tzinfo=_dt.timezone.utc)

    pricing = PricingSettings.current()
    logs = ApiUsageLog.objects.filter(tenant=tenant, created_at__gte=period_start, created_at__lt=period_end)
    rows = []
    total = pricing.monthly_base_fee
    row_cost = ExpressionWrapper(F('units') * F('unit_price'),
                                 output_field=DecimalField(max_digits=14, decimal_places=4))
    for action, label in ApiUsageLog.ACTION_CHOICES:
        action_logs = logs.filter(action=action)
        units = action_logs.aggregate(n=Sum('units'))['n'] or 0
        snapshot_cost = (action_logs.filter(unit_price__isnull=False)
                         .aggregate(c=Sum(row_cost))['c'] or Decimal('0'))
        legacy_units = (action_logs.filter(unit_price__isnull=True)
                        .aggregate(n=Sum('units'))['n'] or 0)
        cost = snapshot_cost + ApiUsageLog.cost_for(action, legacy_units, pricing)
        total += cost
        rows.append({'action': action, 'label': label, 'units': units,
                     'unit_price': ApiUsageLog.cost_for(action, 1, pricing), 'cost': cost})
    return {
        'currency': pricing.currency,
        'year': year,
        'month': month,
        'base_fee': pricing.monthly_base_fee,
        'rows': rows,
        'total': total,
        'pricing': pricing,
    }


class CreditCheckAccess(models.Model):
    """Tracks a tenant's paid access window to a specific client's DCC credit data.
    One row per (tenant, client_cuid) pair per billing event. Access is valid until
    expires_at; after expiry a new View Data click creates a fresh row and bills again."""
    tenant = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='credit_check_accesses')
    client_cuid = models.CharField(max_length=100, help_text='CUID of the client whose credit data was unlocked.')
    accessed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=['tenant', 'client_cuid', 'expires_at'])]

    def __str__(self):
        return f'{self.tenant} → {self.client_cuid} (expires {self.expires_at:%Y-%m-%d %H:%M})'

    @property
    def is_valid(self):
        from django.utils import timezone
        return timezone.now() < self.expires_at


def open_access(tenant, cuid):
    """The single pay-per-view unlock service, shared by the tenant API
    (loanmasta 'View Data') and DCC's own web screens so both channels bill
    identically. Returns (access, created): reuses an open window without
    re-billing, otherwise opens a fresh one and meters a CREDIT_CHECK."""
    from django.utils import timezone as _tz
    from datetime import timedelta as _td

    access = (CreditCheckAccess.objects
              .filter(tenant=tenant, client_cuid=str(cuid), expires_at__gt=_tz.now())
              .order_by('-expires_at').first())
    if access is not None:
        return access, False
    hours = tenant.credit_check_window_hours or 12
    access = CreditCheckAccess.objects.create(
        tenant=tenant, client_cuid=str(cuid),
        expires_at=_tz.now() + _td(hours=hours),
    )
    log_usage(tenant, 'CREDIT_CHECK', detail=str(cuid))
    return access, True


class BillingSettings(models.Model):
    """Invoicing behaviour. One row (the latest is used), editable from the
    SaaS Admin invoices screen."""
    updated_at = models.DateTimeField(auto_now=True)
    auto_send_enabled = models.BooleanField(default=False, help_text="When on, last month's invoice is generated and emailed to every active tenant automatically on the send day.")
    send_day = models.PositiveIntegerField(default=3, help_text='Day of the month (1-28) the automatic invoice run fires.')
    cc_email = models.CharField(max_length=255, blank=True, default='', help_text='Optional address CC-ed on every invoice email.')

    class Meta:
        verbose_name = 'Billing settings'
        verbose_name_plural = 'Billing settings'

    def __str__(self):
        state = 'auto-send ON' if self.auto_send_enabled else 'auto-send OFF'
        return f'DCC billing ({state}, day {self.send_day})'

    @classmethod
    def current(cls):
        return cls.objects.order_by('-updated_at').first() or cls()


class Invoice(models.Model):
    """A tenant's DCC bill for one month, frozen at generation time from the
    usage summary (which itself uses per-row price snapshots)."""
    STATUS_CHOICES = [('DRAFT', 'DRAFT'), ('SENT', 'SENT'), ('PAID', 'PAID')]

    tenant = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='invoices')
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    number = models.CharField(max_length=30, unique=True)
    currency = models.CharField(max_length=10, default='PGK')
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    lines = models.JSONField(default=list, help_text='[{action, label, units, unit_price, cost}, ...]')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('tenant', 'year', 'month')]
        ordering = ['-year', '-month', 'tenant_id']

    def __str__(self):
        return f'{self.number} — {self.tenant} {self.year}-{self.month:02d} ({self.currency} {self.total})'

    @property
    def period_label(self):
        import calendar
        return f'{calendar.month_name[self.month]} {self.year}'


def generate_invoice(tenant, year, month):
    """Create (or refresh, while still DRAFT) the tenant's invoice for a
    month from the usage summary. Sent/paid invoices are never rewritten."""
    summary = usage_summary(tenant, year, month)
    existing = Invoice.objects.filter(tenant=tenant, year=year, month=month).first()
    if existing is not None and existing.status != 'DRAFT':
        return existing

    lines = [{'action': r['action'], 'label': r['label'], 'units': int(r['units']),
              'unit_price': str(r['unit_price']), 'cost': str(r['cost'])}
             for r in summary['rows']]
    total = summary['total'].quantize(Decimal('0.01'))

    if existing is None:
        seq = Invoice.objects.filter(year=year, month=month).count() + 1
        number = f'DCC-{year}{month:02d}-{seq:04d}'
        existing = Invoice(tenant=tenant, year=year, month=month, number=number)
    existing.currency = summary['currency']
    existing.base_fee = summary['base_fee']
    existing.lines = lines
    existing.total = total
    existing.save()
    return existing


def send_invoice(invoice, cc_email=''):
    """Email the invoice to the tenant (account email + org work email).
    Marks it SENT. Raises on email failure so callers can report it."""
    from django.conf import settings as dj_settings
    from django.core.mail import EmailMultiAlternatives
    from django.utils import timezone as _tz

    tenant = invoice.tenant
    recipients = [e for e in {tenant.user.email, tenant.email, tenant.work_email} if e]
    if not recipients:
        raise ValueError(f'Tenant {tenant} has no email address on file.')

    line_rows = ''.join(
        f"<tr><td style='padding:4px 12px;'>{l['label']}</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{l['units']}</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{l['unit_price']}</td>"
        f"<td style='padding:4px 12px;text-align:right;'>{l['cost']}</td></tr>"
        for l in invoice.lines if int(l.get('units') or 0) > 0
    ) or "<tr><td colspan='4' style='padding:4px 12px;'>No metered usage this period.</td></tr>"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;">
      <h2>Dinau Control Center — Invoice {invoice.number}</h2>
      <p>Billing period: <strong>{invoice.period_label}</strong><br>
         Tenant: <strong>{tenant}</strong> (LUID {tenant.LUID})</p>
      <table style="border-collapse:collapse;width:100%;border:1px solid #ddd;">
        <tr style="background:#f4f4f4;">
          <th style='padding:6px 12px;text-align:left;'>Service</th>
          <th style='padding:6px 12px;text-align:right;'>Units</th>
          <th style='padding:6px 12px;text-align:right;'>Unit price ({invoice.currency})</th>
          <th style='padding:6px 12px;text-align:right;'>Cost ({invoice.currency})</th>
        </tr>
        {line_rows}
        <tr><td style='padding:6px 12px;'><strong>Monthly base fee</strong></td><td></td><td></td>
            <td style='padding:6px 12px;text-align:right;'><strong>{invoice.base_fee}</strong></td></tr>
        <tr style="background:#f4f4f4;"><td style='padding:6px 12px;'><strong>TOTAL DUE</strong></td><td></td><td></td>
            <td style='padding:6px 12px;text-align:right;'><strong>{invoice.currency} {invoice.total}</strong></td></tr>
      </table>
      <p style="color:#777;font-size:12px;">Pay-per-view charges are listed per credit-report view in your
      Billing &amp; Usage page. Thank you for using the Dinau Control Center credit bureau.</p>
    </div>"""

    subject = f'DCC Invoice {invoice.number} — {invoice.period_label}'
    email = EmailMultiAlternatives(subject, f'DCC invoice {invoice.number}: {invoice.currency} {invoice.total} due for {invoice.period_label}.',
                                   dj_settings.DEFAULT_FROM_EMAIL, recipients,
                                   cc=[cc_email] if cc_email else None)
    email.attach_alternative(html, 'text/html')
    email.send()

    invoice.status = 'SENT' if invoice.status != 'PAID' else invoice.status
    invoice.sent_at = _tz.now()
    invoice.save(update_fields=['status', 'sent_at'])
    return invoice


def log_usage(tenant, action, units=1, detail=None):
    """Record a billable interaction with the unit price snapshotted at event
    time; never let metering break the API call."""
    if tenant is None:
        return
    try:
        unit_price = ApiUsageLog.cost_for(action, 1, PricingSettings.current())
        ApiUsageLog.objects.create(tenant=tenant, action=action,
                                   units=max(int(units), 0) or 0, detail=detail,
                                   unit_price=unit_price)
    except Exception:
        pass
