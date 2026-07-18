from django.urls import path, re_path

from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('credit_rating/', views.credit_rating, name='credit_rating'),
    path('database-overview/', views.database_overview, name='database_overview'),
    path('database-search/', views.database_search, name='database_search'),
    path('database-search-redirect/<str:search_string>/', views.database_search_redirect, name='database_search_redirect'),
    
    path('my-records/', views.my_records, name='my_records'),
    path('client/<int:client_id>/', views.client_detail, name='client_detail'),
    path('public-default-list/', views.public_listing, name='public_listing'),
    path('search/', views.front_search, name='front_search'),
    path('view-client/<int:client_id>/', views.view_client_record_front, name='view_client_record_front'),
    # Other URL patterns

    path('support/', views.support, name='support'),
    path('login_user/', views.login_user, name='login_user'),
    path('logout_user/', views.logout_user, name='logout_user'),
    path('profile/', views.profile, name='profile'),
    path('activate_user/<int:uid>/', views.activate_user, name='activate_user'),
    path('deactivate_user/<int:uid>/', views.deactivate_user, name='deactivate_user'),
    path('suspend_user/<int:uid>/', views.suspend_user, name='suspend_user'),
    path('edit-contact-info/', views.edit_contact_info, name='edit_contact_info'),

 
    path('edit-uploads/', views.edit_uploads, name='edit_uploads'),

    path('edit-organisation-info/', views.edit_organisation_info, name='edit_organisation_info'),
    
    path('activation_sent/', views.activation_sent, name="activation_sent"),
    path('activate/<slug:uidb64>/<slug:token>/', views.activate, name='activate'),
    path('invalid/', views.activation_invalid, name="activation_invalid"),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('billing/', views.my_billing, name='my_billing'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path('reset_link_sent/', views.reset_link_sent, name='reset_link_sent'),
    path('password_reset/<slug:uidb64>/<slug:token>/', views.password_reset, name='password_reset'),
    path('messages_user/', views.messages_user, name='messages_user'),

]

