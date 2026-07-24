from django.urls import path
from . import views

urlpatterns = [
    path('', views.sa_dashboard, name='sa_dashboard'),
    path('sync-all/', views.sa_sync_all, name='sa_sync_all'),

    # Tenants
    path('tenants/', views.sa_tenants, name='sa_tenants'),
    path('tenants/create/', views.sa_tenant_create, name='sa_tenant_create'),
    path('tenants/<int:tenant_id>/', views.sa_tenant_detail, name='sa_tenant_detail'),
    path('tenants/<int:tenant_id>/sync/', views.sa_sync_tenant, name='sa_sync_tenant'),
    path('tenants/<int:tenant_id>/toggle-active/', views.sa_tenant_toggle_active, name='sa_tenant_toggle_active'),
    path('tenants/<int:tenant_id>/delete/', views.sa_tenant_delete, name='sa_tenant_delete'),

    # Billing & Pricing
    path('billing/', views.sa_billing, name='sa_billing'),
    path('billing/tenant/<int:tenant_id>/', views.sa_tenant_usage, name='sa_tenant_usage'),
    path('pricing/', views.sa_pricing, name='sa_pricing'),
    path('invoices/', views.sa_invoices, name='sa_invoices'),
    path('rating-calculation/', views.sa_rating_rules, name='sa_rating_rules'),
    path('identity/', views.sa_identity, name='sa_identity'),
    path('identity/<int:case_id>/', views.sa_identity_case, name='sa_identity_case'),

    # Users
    path('users/', views.sa_users, name='sa_users'),
    path('users/<int:user_id>/toggle-active/', views.sa_user_toggle_active, name='sa_user_toggle_active'),

    # Client records
    path('clients/', views.sa_clients, name='sa_clients'),
    path('clients/<int:client_id>/', views.sa_client_detail, name='sa_client_detail'),
    path('clients/<int:client_id>/history/', views.sa_client_history, name='sa_client_history'),

    # Loan records
    path('loans/', views.sa_loans, name='sa_loans'),
    path('loans/<str:ref>/', views.sa_loan_detail, name='sa_loan_detail'),

    # Transactions
    path('transactions/', views.sa_transactions, name='sa_transactions'),

    # Website tools
    path('delist-requests/', views.sa_delist_requests, name='sa_delist_requests'),
    path('subscribers/', views.sa_subscribers, name='sa_subscribers'),

    # DCC report
    path('dcc-report/', views.sa_dcc_report, name='sa_dcc_report'),

    # Platform settings
    path('settings/', views.sa_settings, name='sa_settings'),

    # Third-party API key management
    path('tp-api-keys/', views.sa_tp_api_keys, name='sa_tp_api_keys'),

    # Default notices & disputes
    path('default-notices/', views.sa_default_notices, name='sa_default_notices'),
    path('disputes/', views.sa_disputes, name='sa_disputes'),

    # Workflow — Upload, Verification, Settlements
    path('upload-records/', views.sa_upload_records, name='sa_upload_records'),
    path('records-under-review/', views.sa_records_under_review, name='sa_records_under_review'),
    path('records-under-review/<int:case_id>/', views.sa_verification_case, name='sa_verification_case'),
    path('business-records-under-review/', views.sa_business_records_under_review, name='sa_business_records_under_review'),
    path('default-submissions/', views.sa_default_submissions, name='sa_default_submissions'),
    path('settlements/', views.sa_settlements, name='sa_settlements'),
    path('settlements/<int:settlement_id>/', views.sa_settlement_detail, name='sa_settlement_detail'),
]
