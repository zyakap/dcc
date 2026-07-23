from django.urls import path, re_path

from . import views

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/create/', views.admin_create_user, name='admin_create_user'),
    path('clients/', views.admin_clients, name='admin_clients'),
    path('clients/<int:client_id>/', views.admin_view_client, name='admin_view_client'),
    path('clients/<int:client_id>/history/', views.admin_client_history, name='admin_client_history'),
    path('clients/<int:client_id>/dcc-access/', views.admin_dcc_credit_access, name='admin_dcc_credit_access'),
    path('loans/', views.admin_loans, name='admin_loans'),
    path('loans/<str:ref>/', views.admin_loan_detail, name='admin_loan_detail'),
    path('transactions/', views.admin_transactions, name='admin_transactions'),
    path('retrieve/', views.admin_retrieve, name='admin_retrieve'),

    #tenant integration
    path('tenants/', views.admin_tenants, name='admin_tenants'),
    path('tenants/<int:tenant_id>/', views.admin_tenant_config, name='admin_tenant_config'),
    path('usage/', views.admin_usage_metrics, name='admin_usage_metrics'),
    path('dcc-report/', views.admin_dcc_report, name='admin_dcc_report'),

    #action
    path('client-records/upload/', views.admin_upload_client_records, name='admin_upload_client_records'),
    path('client-records/under-review/', views.admin_client_records_under_review, name='admin_client_records_under_review'),
    path('business-records/under-review/', views.admin_business_records_under_review, name='admin_business_records_under_review'),
    path('default-list-submission/', views.admin_default_list_submission, name='admin_default_list_submission'),

]

