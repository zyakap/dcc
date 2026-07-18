from django.urls import path
from . import views


urlpatterns = [
    path('get_clientprofile/<str:uid>/', views.get_clientprofile, name='get_clientprofile'),
    path('get_client_loans/<str:uid>/', views.get_client_loans, name='get_client_loans'),
    path('get_client_transactions/<str:uid>/', views.get_client_transactions, name='get_client_transactions'),
    path('credit_check/<str:uid>/', views.credit_check, name='credit_check'),
    path('credit_check/<str:uid>/unlock/', views.credit_check_unlock, name='credit_check_unlock'),
    path('credit_rating/<str:uid>/', views.credit_rating, name='api_credit_rating'),
    path('billing_summary/', views.billing_summary, name='billing_summary'),
]
