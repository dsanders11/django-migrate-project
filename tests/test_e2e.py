from __future__ import unicode_literals

import os
import shutil

from django.conf import settings
from django.core.management import call_command
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase

from django_migrate_project.loader import (
    DEFAULT_PENDING_MIGRATIONS_DIRECTORY, PROJECT_MIGRATIONS_MODULE_NAME
)


DEFAULT_DIR = os.path.join(
    settings.BASE_DIR, DEFAULT_PENDING_MIGRATIONS_DIRECTORY)
MIGRATIONS_DIR = os.path.join(
    settings.BASE_DIR, PROJECT_MIGRATIONS_MODULE_NAME)


class MigrateProjectTest(TransactionTestCase):
    """ End-to-end tests for django-migrate-project """

    def setUp(self):
        # Delete any created migrations
        try:
            for filename in os.listdir(MIGRATIONS_DIR):
                if filename != '__init__.py':
                    filepath = os.path.join(MIGRATIONS_DIR, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                    else:
                        shutil.rmtree(filepath)
        except IOError:
            pass

        # Delete the default migrations path if it exists
        if os.path.exists(DEFAULT_DIR):
            shutil.rmtree(DEFAULT_DIR)

        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)
        call_command('migrate', 'newspaper', 'zero', verbosity=0)
        call_command('migrate', 'event_calendar', 'zero', verbosity=0)

    def tearDown(self):
        # Delete any created migrations
        try:
            for filename in os.listdir(MIGRATIONS_DIR):
                if filename != '__init__.py':
                    filepath = os.path.join(MIGRATIONS_DIR, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                    else:
                        shutil.rmtree(filepath)
        except IOError:
            pass

        # Delete the default migrations path if it exists
        if os.path.exists(DEFAULT_DIR):
            shutil.rmtree(DEFAULT_DIR)

    def test_collect_end_to_end(self):
        """ Test the collect and migrate functionality end-to-end """

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = loader.applied_migrations

        self.assertNotIn('blog', [app for app, _ in applied_migrations])
        self.assertNotIn('cookbook', [app for app, _ in applied_migrations])
        self.assertNotIn('event_calendar', [app for app, _ in applied_migrations])
        self.assertNotIn('newspaper', [app for app, _ in applied_migrations])

        # Collect migrations and migrate the test project
        call_command('collectmigrations', verbosity=0)
        call_command('applymigrations', verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        applied_migrations = loader.applied_migrations

        # These apps already had migrations so they were collected and run
        self.assertIn('blog', [app for app, _ in applied_migrations])
        self.assertIn('cookbook', [app for app, _ in applied_migrations])

        # These apps didn't have migrations so they were not collected and run
        self.assertNotIn('event_calendar', [app for app, _ in applied_migrations])
        self.assertNotIn('newspaper', [app for app, _ in applied_migrations])

    def test_project_end_to_end(self):
        """ Test the project-level migrations functionality end-to-end """

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = loader.applied_migrations

        self.assertNotIn('blog', [app for app, _ in applied_migrations])
        self.assertNotIn('cookbook', [app for app, _ in applied_migrations])
        self.assertNotIn('event_calendar', [app for app, _ in applied_migrations])
        self.assertNotIn('newspaper', [app for app, _ in applied_migrations])

        # Make project migrations and migrate the test project
        call_command('makeprojectmigrations', verbosity=0)
        call_command('migrateproject', verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        applied_migrations = loader.applied_migrations

        # These apps already had migrations so make migration wouldn't do work
        self.assertNotIn('blog', [app for app, _ in applied_migrations])
        self.assertNotIn('cookbook', [app for app, _ in applied_migrations])

        # These apps didn't have migrations so they were created for project
        self.assertIn('event_calendar', [app for app, _ in applied_migrations])
        self.assertIn('newspaper', [app for app, _ in applied_migrations])
