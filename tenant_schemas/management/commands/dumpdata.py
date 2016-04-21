from django.conf import settings
from django.db import connection

from django.core.management.commands import dumpdata


class Command(dumpdata.Command):

    def handle(self, *args, **options):
        connection.set_schema(self.schema_name)
        super(Command, self).handle(*args, **options)
        connection.set_schema_to_public()
