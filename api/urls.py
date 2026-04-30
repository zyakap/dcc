from django.urls import include, path, re_path
from . import views



urlpatterns = [
    path('get_clientprofile/<str:uid>/', views.get_clientprofile, name='get_clientprofile'),
    path('get_client_loans/<str:uid>/', views.get_client_loans, name='get_client_loans'),
    path('get_client_transactions/<str:uid>/', views.get_client_transactions, name='get_client_transactions'),

]
