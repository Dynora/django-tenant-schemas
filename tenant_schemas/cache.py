from django.db import connection


def make_key(key, key_prefix, version):
    """
    Tenant aware function to generate a cache key.

    Constructs the key used by all other methods. Prepends the tenant
    `schema_name` and `key_prefix'.
    """
    return '%s:%s:%s:%s' % (connection.schema_name, key_prefix, version, key)


def make_tenant_session_key(key, key_prefix, version):
    """
    When supporting tenancy through the user's session, we should make sure all
    session keys written by django.contrib.sessions are stored using a global prefix. We wont have collisions as session
    identifiers are already unique by themselves.

    Constructs the key used by all other methods. Prepends the tenant
    `schema_name` and `key_prefix'.
    """
    if key.startswith('django.contrib.sessions'):
        prefix = '__tenant_session__'
    else:
        prefix = connection.schema_name
    return '%s:%s:%s:%s' % (prefix, key_prefix, version, key)


def reverse_key(key):
    """
    Tenant aware function to reverse a cache key.

    Required for django-redis REVERSE_KEY_FUNCTION setting.
    """
    return key.split(':', 3)[3]
