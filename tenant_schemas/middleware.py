from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import Http404
from tenant_schemas.utils import (get_tenant_model, remove_www,
                                  get_public_schema_name)


class TenantMiddleware(object):
    """
    This middleware should be placed at the very top of the middleware stack.
    Selects the proper database schema using the request host. Can fail in
    various ways which is better than corrupting or revealing data.
    """
    TENANT_NOT_FOUND_EXCEPTION = Http404

    def hostname_from_request(self, request):
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """
        return remove_www(request.get_host().split(':')[0])

    def process_request(self, request):
        # Connection needs first to be at the public schema, as this is where
        # the tenant metadata is stored.
        connection.set_schema_to_public()
        TenantModel = get_tenant_model()

        request.tenant = None
        if hasattr(request, 'user') and not request.user.is_anonymous() and request.user.is_authenticated():
            try:
                request.tenant = TenantModel.objects.get(id=request.user.client_id, is_active=True)
            except TenantModel.DoesNotExist:
                pass

        if request.tenant:
            connection.set_tenant(request.tenant)
        else:
            request.tenant = TenantModel.objects.get(schema_name=settings.DEFAULT_TENANT_SCHEMA)
            connection.set_tenant(request.tenant)

        # Content type can no longer be cached as public and tenant schemas
        # have different models. If someone wants to change this, the cache
        # needs to be separated between public and shared schemas. If this
        # cache isn't cleared, this can cause permission problems. For example,
        # on public, a particular model has id 14, but on the tenants it has
        # the id 15. if 14 is cached instead of 15, the permissions for the
        # wrong model will be fetched.
        ContentType.objects.clear_cache()

        # Do we have a public-specific urlconf?
        if hasattr(settings, 'PUBLIC_SCHEMA_URLCONF') and request.tenant.schema_name == get_public_schema_name():
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF


class SuspiciousTenantMiddleware(TenantMiddleware):
    """
    Extend the TenantMiddleware in scenario where you need to configure
    ``ALLOWED_HOSTS`` to allow ANY domain_url to be used because your tenants
    can bring any custom domain with them, as opposed to all tenants being a
    subdomain of a common base.

    See https://github.com/bernardopires/django-tenant-schemas/pull/269 for
    discussion on this middleware.
    """
    TENANT_NOT_FOUND_EXCEPTION = DisallowedHost
