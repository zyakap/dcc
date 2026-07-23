from django.urls import path
from . import views

urlpatterns = [
    path('login/',    views.borrower_login,    name='borrower_login'),
    path('logout/',   views.borrower_logout,   name='borrower_logout'),
    path('',          views.borrower_dashboard, name='borrower_dashboard'),
    path('enquiries/', views.borrower_enquiries, name='borrower_enquiries'),
    path('disputes/', views.borrower_disputes,  name='borrower_disputes'),
    path('consents/', views.borrower_consents,  name='borrower_consents'),
]
