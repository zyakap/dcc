"""Machine-to-machine authentication for DCC's tenant-facing API.

A tenant LMS (e.g. LoanMasta / Wincorp Finance) must send:
    X-API-KEY:      the shared secret configured for it in the DCC control panel
    X-TENANT-LUID:  its LUID (identifies which tenant is calling)

The key is compared against ``users.UserProfile.api_key`` for that LUID in
constant time. Fails closed: tenants without a configured key are denied.
The matched tenant profile is attached to the request as ``request.tenant``
so views can meter usage per tenant.
"""
import hmac

from rest_framework.permissions import BasePermission

from users.models import UserProfile


class TenantAPIKey(BasePermission):
    message = 'Valid X-API-KEY and X-TENANT-LUID headers are required.'

    def has_permission(self, request, view):
        luid = request.META.get('HTTP_X_TENANT_LUID', '') or ''
        provided = request.META.get('HTTP_X_API_KEY', '') or ''
        if not luid or not provided:
            return False
        tenant = UserProfile.objects.filter(LUID=luid).first()
        if tenant is None or not tenant.api_key:
            return False
        if not hmac.compare_digest(str(tenant.api_key), str(provided)):
            return False
        request.tenant = tenant
        return True
