from django.apps import apps
from django.conf import settings
from django.db.models.base import ModelBase


class TenantSyncRouter(object):
    """
    A router to control which applications will be synced,
    depending if we are syncing the shared apps or the tenant apps.
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # the imports below need to be done here else django <1.5 goes crazy
        # https://code.djangoproject.com/ticket/20704
        from django.db import connection
        from tenant_schemas.utils import get_public_schema_name, app_labels

        if isinstance(app_label, ModelBase):
            # In django <1.7 the `app_label` parameter is actually `model`
            app_label = app_label._meta.app_label

        if connection.schema_name == get_public_schema_name():
            if app_label not in app_labels(settings.SHARED_APPS):
                return False
        else:
            if app_label not in app_labels(settings.TENANT_APPS):
                return False

        if model_name:
            model = apps.get_model(app_label=app_label, model_name=model_name)
            if hasattr(model, '__schema_name__') and model.__schema_name__:

                conn_schema = connection.tenant.schema_name.strip()
                if conn_schema == 'public' and conn_schema != model.__schema_name__ or \
                   conn_schema != 'public' and model.__schema_name__ == 'public':
                    return False

        return None

    def allow_syncdb(self, db, model):
        # allow_syncdb was changed to allow_migrate in django 1.7
        return self.allow_migrate(db, model)
