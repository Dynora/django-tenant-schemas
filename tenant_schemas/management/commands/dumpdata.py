from django.db import connection

from django.core.management.commands import dumpdata


class Command(dumpdata.Command):

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--schema', default='public', dest='schema', help='Specifies the schema to dump data for.')

    def handle(self, *args, **options):
        schema = options.get('schema')
        connection.set_schema(schema)
        super(Command, self).handle(*args, **options)
        connection.set_schema_to_public()
