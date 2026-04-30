from django.urls import path, re_path

from . import views

urlpatterns = [
    path('get_transactions/<str:endpoint_url>/', views.get_transactions, name='get_transactions')
]