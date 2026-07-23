import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class ThirdPartyApiKey(models.Model):
    PERMISSIONS_CHOICES = [
        ('credit_report',  'Full Credit Report'),
        ('score_only',     'Credit Score Only'),
        ('consent_write',  'Record Consent'),
        ('enquiry_log',    'Own Enquiry Log'),
    ]

    name          = models.CharField(max_length=100)
    contact_name  = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True)
    key_hash      = models.CharField(max_length=255)
    key_prefix    = models.CharField(max_length=10, unique=True)
    permissions   = models.JSONField(default=list, help_text='List of allowed scope strings')
    rate_limit_per_day = models.PositiveIntegerField(default=1000)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    last_used     = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Third-party API key'

    def __str__(self):
        return f'{self.name} ({self.key_prefix}…)'

    def verify_key(self, raw_key):
        return check_password(raw_key, self.key_hash)

    def has_permission(self, perm):
        return perm in (self.permissions or [])

    @classmethod
    def generate(cls, name, contact_email='', permissions=None):
        raw = 'tpk_' + secrets.token_hex(28)
        prefix = raw[:10]
        inst = cls.objects.create(
            name=name,
            contact_email=contact_email,
            key_hash=make_password(raw),
            key_prefix=prefix,
            permissions=permissions or ['credit_report'],
        )
        return inst, raw


class TpApiUsageLog(models.Model):
    api_key    = models.ForeignKey(ThirdPartyApiKey, on_delete=models.CASCADE, related_name='usage_logs')
    endpoint   = models.CharField(max_length=100)
    cuid       = models.CharField(max_length=100, blank=True)
    status     = models.PositiveIntegerField(default=200)
    queried_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes   = [models.Index(fields=['api_key', '-queried_at'])]
        ordering  = ['-queried_at']
