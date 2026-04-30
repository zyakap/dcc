from django.urls import path, re_path

from . import views

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('users/', views.admin_users, name='admin_users'),
    path('users/create/', views.admin_create_user, name='admin_create_user'),
    path('clients/', views.admin_clients, name='admin_clients'),
    path('loans/', views.admin_loans, name='admin_loans'),
    path('transactions/', views.admin_transactions, name='admin_transactions'),
    path('retrieve/', views.admin_retrieve, name='admin_retrieve'),

    #action
    path('client-records/upload/', views.admin_upload_client_records, name='admin_upload_client_records'),
    path('client-records/under-review/', views.admin_client_records_under_review, name='admin_client_records_under_review'),
    path('business-records/under-review/', views.admin_business_records_under_review, name='admin_business_records_under_review'),
    path('default-list-submission/', views.admin_default_list_submission, name='admin_default_list_submission'),

]

