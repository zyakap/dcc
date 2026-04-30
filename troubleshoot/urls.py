# Media Storage to be served locally
from django.conf import settings
from django.conf.urls.static import static
# others
from django.contrib import admin
from django.urls import include, path, re_path

from users.views import home

urlpatterns = [

    path('appadmin/', admin.site.urls),
    path('__debug__/', include('debug_toolbar.urls')), 
    path('ckeditor/', include('ckeditor_uploader.urls')),

    re_path(r'^$', home, name='home'),
    path('users/', include('users.urls')),
    path('api/', include('api.urls')),
    path('client/', include('client.urls')),
    path('loan/', include('loan.urls')),
    path('transaction/', include('transaction.urls')),

    #Django Jet Admin
    #path('jet/', include('jet.urls', 'jet')),
    #path('jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),
]

# Media Storage to be served locally
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
