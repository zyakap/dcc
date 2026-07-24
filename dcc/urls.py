# Media Storage to be served locally
from django.conf import settings
from django.conf.urls.static import static
# others
from django.urls import include, path, re_path

from users.views import home, terms_conditions, about, contact, front_search, public_listing,submit_default_list,request_delist, request_delist_feedback, newsletter_subscribe, submit_default_list_feedback

urlpatterns = [

    path('__debug__/', include('debug_toolbar.urls')), 
    path('ckeditor/', include('ckeditor_uploader.urls')),

    re_path(r'^$', home, name='home'),
    re_path(r'terms-and-conditions/', terms_conditions, name='terms_conditions'),
    path('users/', include('users.urls')),
    path('api/', include('api.urls')),
    path('API/', include('api.urls')),  # tenant LMS clients call the uppercase form
    path('client/', include('client.urls')),
    path('loan/', include('loan.urls')),
    path('transaction/', include('transaction.urls')),
    # /admin/ and /saasadmin/ both serve the saasadmin control panel
    path('admin/', include('saasadmin.urls')),
    path('saasadmin/', include('saasadmin.urls')),
    path('borrower/',  include('borrower.urls')),
    path('tpapi/v1/', include('thirdparty_api.urls')),
    path('about/', about, name='about'),
    path('contact/', contact, name='contact'),
    path('public-listing/', public_listing, name='public_listing'),
    path('submit_default_list/', submit_default_list, name='submit_default_list'),
    path('request-delist', request_delist, name='request_delist'),
    path('request-delist-feedback', request_delist_feedback, name='request_delist_feedback'),
    path('newsletter-subscribe', newsletter_subscribe, name='newsletter_subscribe'),
    path('submit-default-list-feedback/', submit_default_list_feedback, name='submit_default_list_feedback'),

    path('search/', front_search, name='front_search'),

    #Django Jet Admin
    #path('jet/', include('jet.urls', 'jet')),
    #path('jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),
]

# Media Storage to be served locally
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
