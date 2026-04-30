from django.urls import path, re_path

from . import views

urlpatterns = [
    path('get_loans/<str:endpoint_url>/', views.get_loans, name='get_loans')
]

