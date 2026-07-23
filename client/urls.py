from django.urls import path, re_path

from . import views

urlpatterns = [
    path('get_clientprofiles/<str:endpoint_url>/', views.get_clientprofiles, name='get_clientprofiles'),

    path('view/<int:client_id>/', views.client_record_detail, name='client_record_detail'),
    path('loan/<str:ref>/', views.loan_detail, name='loan_detail'),
    path('view/<int:client_id>/dcc-access/', views.dcc_credit_check_access, name='dcc_credit_check_access'),
    path('business/view/<int:business_id>/', views.business_record_detail, name='business_record_detail'),
    path('client/sample/', views.client_record_detail_sample, name='client_record_detail_sample'),
    path('business/sample/', views.business_record_detail_sample, name='business_record_detail_sample'),

    path('upload-records/', views.upload_records, name='upload_records'),
    path('upload-complete/', views.upload_complete, name='upload_complete'),


    

    path('add-client/', views.add_client, name='add_client'),
    path('add-business/', views.add_business, name='add_business'),
    path('client-records/', views.client_records, name='client_records'),
    path('client-records/under-review/', views.client_records_under_review, name='client_records_under_review'),

    
    path('client-records-dcc/', views.client_records_dcc, name='client_records_dcc'),
    path('recent-client-records/', views.recent_client_records_dcc, name='recent_client_records_dcc'),
    path('business-records/', views.business_records, name='business_records'),
    path('business-records-dcc/', views.business_records_dcc, name='business_records_dcc'),
    path('recovery-insights/', views.recovery_insights, name='recovery_insights'),
    path('filtered-client-records/you-created-today/', views.filtered_client_records_your_records_today, name='filtered_client_records_your_records_today'),
    path('filtered-client-records/you-updated-today/', views.filtered_client_records_your_updated_today, name='filtered_client_records_your_updated_today'),
    path('filtered-business-records/you-created-today/', views.filtered_records_your_business_today, name='filtered_records_your_business_today'),
    
    path('filtered-client-records/dcc-created-today/', views.filtered_client_records_dcc_records_today, name='filtered_client_records_dcc_records_today'),
    path('filtered-client-records/dcc-updated-today/', views.filtered_client_records_dcc_updated_today, name='filtered_client_records_dcc_updated_today'),
    path('filtered-business-records/dcc-created-today/', views.filtered_business_records_dcc_today, name='filtered_business_records_dcc_today'),
    path('filtered-business-records/dcc-updated-today/', views.filtered_business_records_dcc_updated_today, name='filtered_business_records_dcc_updated_today'),

    
    
    path('filtered-loan-records/your-arrears/', views.filtered_loan_records_your_arrears, name='filtered_loan_records_your_arrears'),
    path('filtered-loan-records/dcc-arrears/', views.filtered_loan_records_dcc_arrears, name='filtered_loan_records_dcc_arrears'),
    path('filtered-loan-records/your-defaults/', views.filtered_loan_records_your_defaults, name='filtered_loan_records_your_defaults'),
    path('filtered-loan-records/dcc-defaults/', views.filtered_loan_records_dcc_defaults, name='filtered_loan_records_dcc_defaults'),
    path('filtered-loan-records/your-recovery/', views.filtered_loan_records_your_recovery, name='filtered_loan_records_your_recovery'),
    path('filtered-loan-records/dcc-recovery/', views.filtered_loan_records_dcc_recovery, name='filtered_loan_records_dcc_recovery'),

    # Default notice workflow
    path('view/<int:client_id>/default-notice/submit/', views.submit_default_notice, name='submit_default_notice'),
    path('default-notices/', views.my_default_notices, name='my_default_notices'),

    # Disputes
    path('view/<int:client_id>/dispute/submit/', views.submit_dispute, name='submit_dispute'),

    # Consent
    path('view/<int:client_id>/consent/record/', views.record_consent, name='record_consent'),
    path('view/<int:client_id>/consents/', views.client_consents, name='client_consents'),

    # Credit report PDF
    path('view/<int:client_id>/credit-report.pdf', views.credit_report_pdf, name='credit_report_pdf'),

    # Portfolio analytics
    path('portfolio-analytics/', views.portfolio_analytics, name='portfolio_analytics'),
]

