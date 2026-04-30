from django.contrib import admin

from .models import (
    ClientProfile, BusinessProfile, UserProfileUpload, 
    ClientUpload, ClientAddress, ClientContact, 
    ClientEmployer, ClientBankAccount
)

@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'mobile1', 'client_type', 'credit_rating', 'dcc_status')
    search_fields = ('first_name', 'last_name', 'email', 'nid_number')
    list_filter = ('client_type', 'dcc_status', 'province_of_origin')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ('trading_name', 'registered_name', 'business_owner', 'category', 'credit_rating')
    search_fields = ('trading_name', 'registered_name', 'ipa_registration_number', 'tin_number')
    list_filter = ('category', 'vetting_status')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(UserProfileUpload)
class UserProfileUploadAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'upload_type', 'processed', 'created_at')
    search_fields = ('description',)
    list_filter = ('upload_type', 'processed')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientUpload)
class ClientUploadAdmin(admin.ModelAdmin):
    list_display = ('client', 'upload_type', 'description', 'created_at')
    search_fields = ('description',)
    list_filter = ('upload_type',)
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientAddress)
class ClientAddressAdmin(admin.ModelAdmin):
    list_display = ('client', 'address_type', 'residential_province', 'address')
    search_fields = ('client__first_name', 'client__last_name', 'address')
    list_filter = ('address_type', 'residential_province')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientContact)
class ClientContactAdmin(admin.ModelAdmin):
    list_display = ('client', 'email1', 'mobile1')
    search_fields = ('client__first_name', 'client__last_name', 'email1', 'mobile1')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientEmployer)
class ClientEmployerAdmin(admin.ModelAdmin):
    list_display = ('client', 'employer', 'job_title', 'sector', 'gross_pay')
    search_fields = ('client__first_name', 'client__last_name', 'employer')
    list_filter = ('sector', 'pay_frequency')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ClientBankAccount)
class ClientBankAccountAdmin(admin.ModelAdmin):
    list_display = ('client', 'bank', 'account_number')
    search_fields = ('client__first_name', 'client__last_name', 'account_number')
    list_filter = ('bank',)
    readonly_fields = ('created_at', 'updated_at')
