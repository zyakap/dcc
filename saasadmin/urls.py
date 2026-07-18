from django.urls import path
from . import views

urlpatterns = [
    path('', views.sa_dashboard, name='sa_dashboard'),
    path('sync-all/', views.sa_sync_all, name='sa_sync_all'),

    # Tenants
    path('tenants/', views.sa_tenants, name='sa_tenants'),
    path('tenants/create/', views.sa_tenant_create, name='sa_tenant_create'),
    path('tenants/<int:tenant_id>/', views.sa_tenant_detail, name='sa_tenant_detail'),
    path('tenants/<int:tenant_id>/toggle-active/', views.sa_tenant_toggle_active, name='sa_tenant_toggle_active'),
    path('tenants/<int:tenant_id>/delete/', views.sa_tenant_delete, name='sa_tenant_delete'),

    # Billing & Pricing
    path('billing/', views.sa_billing, name='sa_billing'),
    path('pricing/', views.sa_pricing, name='sa_pricing'),

    # Users
    path('users/', views.sa_users, name='sa_users'),
    path('users/<int:user_id>/toggle-active/', views.sa_user_toggle_active, name='sa_user_toggle_active'),

    # Client records
    path('clients/', views.sa_clients, name='sa_clients'),

    # Loan records
    path('loans/', views.sa_loans, name='sa_loans'),

    # DCC report
    path('dcc-report/', views.sa_dcc_report, name='sa_dcc_report'),

    # Platform settings
    path('settings/', views.sa_settings, name='sa_settings'),
]
