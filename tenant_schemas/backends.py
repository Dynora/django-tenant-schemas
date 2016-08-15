from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from threadlocals.threadlocals import get_current_request
from django.db import connection
from tenant_schemas import get_tenant_user_model


class TenantSessionAuthBackend(ModelBackend):
    """
    An authentication backend that checks wether we should restrict tentant users to the tenant found for the host
    Sets the associated schema in the session.
    Depends on tenant_schemas.middleware.TenantAwareSessionMiddleware
    """

    def authenticate(self, username=None, password=None, **kwargs):
        try:
            TenantUserModel = get_tenant_user_model()
            request = get_current_request()

            extra_kwargs = {}
            if getattr(settings, 'RESTRICT_TENANT_TO_HOST', False):
                if not request.host_tenant:
                    return
                extra_kwargs['%s__schema_name' % settings.TENANT_USER_TENANT_FK] = request.host_tenant.schema_name

            tenant_user = TenantUserModel.objects.select_related(settings.TENANT_USER_TENANT_FK).get(email=username, **extra_kwargs)
            connection.set_tenant(getattr(tenant_user, settings.TENANT_USER_TENANT_FK))
            user = super(TenantSessionAuthBackend, self).authenticate(username=username, password=password, **kwargs)

            if user:
                request.session['__schema_name__'] = getattr(tenant_user, settings.TENANT_USER_TENANT_FK).schema_name

            return user
        except:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a non-existing user (#20760).
            UserModel = get_user_model()
            UserModel().set_password(password)
