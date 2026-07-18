from django.contrib import admin

from .models import ApiUsageLog, PricingSettings


@admin.register(PricingSettings)
class PricingSettingsAdmin(admin.ModelAdmin):
    list_display = ['currency', 'monthly_base_fee', 'price_per_credit_check',
                    'price_per_profile_lookup', 'price_per_record_synced', 'updated_at']


@admin.register(ApiUsageLog)
class ApiUsageLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'tenant', 'action', 'units', 'detail']
    list_filter = ['action', 'tenant']
    date_hierarchy = 'created_at'
