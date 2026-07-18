from decimal import Decimal

from django.db import models

from users.models import UserProfile


class PricingSettings(models.Model):
    """DCC service pricing. One row (the latest is used) — editable from the
    control panel so usage cost can be computed per tenant."""
    updated_at = models.DateTimeField(auto_now=True)
    currency = models.CharField(max_length=10, default='PGK')
    monthly_base_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text='Flat monthly access fee per tenant.')
    price_per_credit_check = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Charged for each consolidated credit check.')
    price_per_profile_lookup = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Charged for each single profile/loans/transactions lookup.')
    price_per_record_synced = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.0000'), help_text='Charged per record ingested from the tenant feed.')

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
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='usage_logs')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    units = models.PositiveIntegerField(default=1, help_text='1 per lookup/check; record count for feed syncs.')
    detail = models.CharField(max_length=255, null=True, blank=True)

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
        return Decimal('0.00')


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


def log_usage(tenant, action, units=1, detail=None):
    """Record a billable interaction; never let metering break the API call."""
    if tenant is None:
        return
    try:
        ApiUsageLog.objects.create(tenant=tenant, action=action, units=max(int(units), 0) or 0, detail=detail)
    except Exception:
        pass
