from __future__ import unicode_literals

import os
import shutil

from django.conf import settings
from django.core.management import call_command
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase


DEFAULT_DIR = os.path.join(settings.BASE_DIR, 'migrations')


class MigrateProjectTest(TransactionTestCase):
    """ End-to-end tests for django-migrate-project """

    def setUp(self):
        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)

    def tearDown(self):
        # Delete the default migrations path if it exists
        if os.path.exists(DEFAULT_DIR):
            shutil.rmtree(DEFAULT_DIR)

    def test_end_to_end(self):
        """ Test the collect and migrate functionality end-to-end """

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = loader.applied_migrations

        self.assertNotIn('blog', [app for app, _ in applied_migrations])
        self.assertNotIn('cookbook', [app for app, _ in applied_migrations])

        # Collect migrations and migrate the test project
        call_command('collectmigrations', verbosity=0)
        call_command('migrateproject', verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        applied_migrations = loader.applied_migrations

        self.assertIn('blog', [app for app, _ in applied_migrations])
        self.assertIn('cookbook', [app for app, _ in applied_migrations])
