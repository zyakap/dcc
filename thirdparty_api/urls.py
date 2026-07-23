from django.urls import path
from . import views

urlpatterns = [
    path('status/',                     views.tp_status,         name='tp_status'),
    path('client/<str:cuid>/score/',    views.tp_credit_score,   name='tp_credit_score'),
    path('client/<str:cuid>/report/',   views.tp_credit_report,  name='tp_credit_report'),
    path('client/<str:cuid>/consent/',  views.tp_record_consent, name='tp_record_consent'),
    path('enquiry-log/',                views.tp_enquiry_log,    name='tp_enquiry_log'),
]
