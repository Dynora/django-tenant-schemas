from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import Http404
from tenant_schemas.utils import (get_tenant_model, remove_www,
                                  get_public_schema_name)


class DummyTenant(object):
    def __init__(self, schema_name):
        self.schema_name = schema


class TenantAwareSessionMiddleware(SessionMiddleware):
    """
    Replaces both TenantMiddleware and django.contrib.sessions.middleware
    Assumes django sessions are global (place django.contrib.sessions in SHARED_APPS if
    """
    TENANT_NOT_FOUND_EXCEPTION = Http404

    def hostname_from_request(self, request):
        """ Extracts hostname from request. Used for custom requests filtering.
            By default removes the request's port and common prefixes.
        """
        return remove_www(request.get_host().split(':')[0])

    def process_request(self, request):
        super(TenantAwareSessionMiddleware, self).process_request(request)

        # Connection needs first to be at the default schema, as we create session keys using this schema name
        TenantModel = get_tenant_model()
        request.tenant = None
        request.host_tenant = None

        try:
            hostname = self.hostname_from_request(request)
            request.host_tenant = TenantModel.objects.get(domain_url=hostname)
        except TenantModel.DoesNotExist:
            pass

        # First check if there is a schema set in the session
        if request.session.get('__schema_name__'):
            try:
                request.tenant = TenantModel.objects.get(schema_name=request.session['__schema_name__'], is_active=True)
            except TenantModel.DoesNotExist:
                raise self.TENANT_NOT_FOUND_EXCEPTION('Invalid tenant stored in session')

        # Fallback to the tenant associated to this host (if any)
        if not request.tenant:
            request.tenant = request.host_tenant

        # If no tenant was set in the request and no tenant could be resolved using the hostname, fallback to the
        # default tenant
        if not request.tenant:
            if settings.DEFAULT_TENANT_SCHEMA == 'public':
                request.tenant = DummyTenant(schema_name='public')
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
        hostname = self.hostname_from_request(request)

        TenantModel = get_tenant_model()
        try:
            request.tenant = TenantModel.objects.get(domain_url=hostname)
            connection.set_tenant(request.tenant)
        except TenantModel.DoesNotExist:
            raise self.TENANT_NOT_FOUND_EXCEPTION(
                'No tenant for hostname "%s"' % hostname)

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
