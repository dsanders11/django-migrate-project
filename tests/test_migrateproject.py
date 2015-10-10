from __future__ import unicode_literals

from copy import copy

import os
import shutil
import sys
import tempfile

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.migrations.loader import MigrationLoader
from django.db.models.signals import post_migrate, pre_migrate
from django.test import override_settings, TransactionTestCase
from django.utils import six

from django_migrate_project.loader import PROJECT_MIGRATIONS_MODULE_NAME

import mock


TEST_MIGRATIONS_DIR = os.path.join(settings.BASE_DIR, 'test_migrations')
PROJECT_MIGRATIONS_DIRECTORY = os.path.join(
    TEST_MIGRATIONS_DIR, 'project_migration')

EXPECTED_MIGRATIONS = sorted([
    '__init__.py',
    'event_calendar_0001_initial.py',
    'newspaper_0001_initial.py'
])

from unittest import skip


class MigrateProjectTest(TransactionTestCase):
    """ Tests for 'migrateproject' """

    def setUp(self):
        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)
        call_command('migrate', 'event_calendar', 'zero', verbosity=0)
        call_command('migrate', 'newspaper', 'zero', verbosity=0)

        self._old_sys_path = copy(sys.path)

    def tearDown(self):
        # Delete any temp directories
        if getattr(self, 'tempdir', None):
            shutil.rmtree(self.tempdir)

        self.clear_migrations_modules()

        sys.path = self._old_sys_path

    def clear_migrations_modules(self):
        # Destroy modules that were loaded for migrations
        sys.modules.pop("blog_0001_project", None)
        sys.modules.pop("cookbook_0001_project", None)
        sys.modules.pop("cookbook_0002_project", None)

    def setup_migration_tree(self, dir):
        # Move the files to the correct location
        shutil.copytree(
            PROJECT_MIGRATIONS_DIRECTORY,
            os.path.join(dir, PROJECT_MIGRATIONS_MODULE_NAME)
        )

        sys.path.insert(0, dir)

        return os.path.join(dir, PROJECT_MIGRATIONS_MODULE_NAME)

    def test_routine_migration(self):
        """ Test applying a routine project migration """

        self.tempdir = tempfile.mkdtemp()

        with override_settings(BASE_DIR=self.tempdir):
            self.setup_migration_tree(settings.BASE_DIR)

            connection = connections[DEFAULT_DB_ALIAS]
            loader = MigrationLoader(connection)
            applied_migrations = copy(loader.applied_migrations)
            migrated_apps = [app for app, _ in loader.applied_migrations]

            self.assertNotIn('event_calendar', migrated_apps)
            self.assertNotIn('newspaper', migrated_apps)

            call_command('migrateproject', verbosity=0)

            try:
                # Check that database changed
                loader = MigrationLoader(connection)
                self.assertNotEqual(
                    loader.applied_migrations, applied_migrations)

                migrated_apps = [app for app, _ in loader.applied_migrations]

                self.assertIn('event_calendar', migrated_apps)
                self.assertIn('newspaper', migrated_apps)
            finally:
                # Roll back migrations to a blank state
                # NOTE: This needs to be done before deleting anything or else
                #       Django won't find the migrations on disk
                call_command('migrate', 'event_calendar', 'zero', verbosity=0)
                call_command('migrate', 'newspaper', 'zero', verbosity=0)

    def test_migrations_dir_error(self):
        """ Test running the management command with a bad migrations dir """

        self.tempdir = tempfile.mkdtemp()

        with override_settings(BASE_DIR=self.tempdir):
            # No migrations folder at all
            with self.assertRaises(CommandError):
                call_command('migrateproject', verbosity=0)

            migrations_dir = self.setup_migration_tree(settings.BASE_DIR)

            os.remove(os.path.join(migrations_dir, '__init__.py'))

            # Missing __init__.py file
            with self.assertRaises(CommandError):
                call_command('migrateproject', verbosity=0)

    def test_unapply(self):
        """ Test unapplying an applied project migration """

        self.tempdir = tempfile.mkdtemp()

        def perform_unapply():
            connection = connections[DEFAULT_DB_ALIAS]
            loader = MigrationLoader(connection)
            applied_migrations = copy(loader.applied_migrations)

            # Apply the migrations, then unapply them
            call_command('migrateproject', verbosity=0)

            # Check that database changed
            loader = MigrationLoader(connection)
            self.assertNotEqual(
                loader.applied_migrations, applied_migrations)

            migrated_apps = [app for app, _ in loader.applied_migrations]

            self.assertIn('event_calendar', migrated_apps)
            self.assertIn('newspaper', migrated_apps)

            out = six.StringIO()

            # Call command to unapply the changes
            call_command('migrateproject', unapply=True, stdout=out,
                         verbosity=1)

            # Check that it says it was unapplied
            self.assertIn("unapply all", out.getvalue().lower())

            # Check that database is back to original
            loader = MigrationLoader(connection)
            migrated_apps = [app for app, _ in loader.applied_migrations]

            self.assertEqual(loader.applied_migrations, applied_migrations)
            self.assertNotIn('event_calendar', migrated_apps)
            self.assertNotIn('newspaper', migrated_apps)

        with override_settings(BASE_DIR=self.tempdir):
            self.setup_migration_tree(settings.BASE_DIR)

            field = None

            try:
                # Do a normal unapply
                perform_unapply()

                # Then make some new changes via monkey patching
                from event_calendar.models import Event

                for field in Event._meta.fields:
                    if field.name == 'description':
                        field.blank = True
                        field.null = True
                        break

                out = six.StringIO()

                # Create the new migration
                call_command('makeprojectmigrations', stdout=out, verbosity=1)
                self.assertIn("migrations for", out.getvalue().lower())

                # The cached package won't see the new module
                sys.modules.pop("migrations", None)

                # And apply/unapply those new migrations for better
                # statement coverage
                perform_unapply()
            finally:
                if field:
                    field.blank = False
                    field.null = False

                # Roll back migrations to a blank state
                # NOTE: This needs to be done before deleting anything or else
                #       Django won't find the migrations on disk
                call_command('migrate', 'event_calendar', 'zero', verbosity=0)
                call_command('migrate', 'newspaper', 'zero', verbosity=0)

    def test_nothing_to_apply(self):
        """ Test applying already applied project migration """

        self.tempdir = tempfile.mkdtemp()

        with override_settings(BASE_DIR=self.tempdir):
            self.setup_migration_tree(settings.BASE_DIR)

            connection = connections[DEFAULT_DB_ALIAS]
            loader = MigrationLoader(connection)
            applied_migrations = copy(loader.applied_migrations)
            migrated_apps = [app for app, _ in loader.applied_migrations]

            self.assertNotIn('event_calendar', migrated_apps)
            self.assertNotIn('newspaper', migrated_apps)

            call_command('migrateproject', verbosity=0)

            try:
                # Check that database changed
                loader = MigrationLoader(connection)
                self.assertNotEqual(
                    loader.applied_migrations, applied_migrations)

                out = six.StringIO()

                # Call command again to show nothing changes
                call_command('migrateproject', stdout=out, verbosity=1)

                self.assertIn('no migrations', out.getvalue().lower())
            finally:
                # Roll back migrations to a blank state
                # NOTE: This needs to be done before deleting anything or else
                #       Django won't find the migrations on disk
                call_command('migrate', 'event_calendar', 'zero', verbosity=0)
                call_command('migrate', 'newspaper', 'zero', verbosity=0)

    def test_signals(self):
        """ Test the signals emitted during the migration """

        app_config = apps.get_app_config('event_calendar')

        pre_migrate_callback = mock.MagicMock()
        post_migrate_callback = mock.MagicMock()

        pre_migrate.connect(pre_migrate_callback, sender=app_config)
        post_migrate.connect(post_migrate_callback, sender=app_config)

        self.test_routine_migration()

        pre_migrate.disconnect(pre_migrate_callback, sender=app_config)
        post_migrate.disconnect(post_migrate_callback, sender=app_config)

        self.assertEqual(pre_migrate_callback.call_count, 3)
        self.assertEqual(post_migrate_callback.call_count, 3)

    def test_changes_detected(self):
        """ Test a migration with model changes detected """

        self.tempdir = tempfile.mkdtemp()

        module = 'django_migrate_project.management.commands.migrateproject'
        changes_path = module + '.MigrationAutodetector.changes'

        with override_settings(BASE_DIR=self.tempdir):
            self.setup_migration_tree(settings.BASE_DIR)

            # Migrate first, so that no migrations are available to apply
            call_command('migrateproject', verbosity=0)

            try:
                with mock.patch(changes_path) as changes:
                    changes.return_value = True

                    out = six.StringIO()
                    call_command('migrateproject', stdout=out, verbosity=1)

                    output = out.getvalue().lower()

                    self.assertIn("have changes", output)
                    self.assertIn("'manage.py makeprojectmigrations'", output)
                    self.assertIn("'manage.py migrateproject'", output)
            finally:
                # Roll back migrations to a blank state
                # NOTE: This needs to be done before deleting anything or else
                #       Django won't find the migrations on disk
                call_command('migrate', 'event_calendar', 'zero', verbosity=0)
                call_command('migrate', 'newspaper', 'zero', verbosity=0)

    def test_alt_database(self):
        """ Test migrating a project with an alternate database selected """

        self.tempdir = tempfile.mkdtemp()

        with override_settings(BASE_DIR=self.tempdir):
            self.setup_migration_tree(settings.BASE_DIR)

            # Roll back migrations to a blank state in the 'other' database
            call_command('migrate', 'event_calendar', 'zero', database='other',
                         verbosity=0)
            call_command('migrate', 'newspaper', 'zero', database='other',
                         verbosity=0)

            default_connection = connections[DEFAULT_DB_ALIAS]
            connection = connections['other']

            default_loader = MigrationLoader(default_connection)
            loader = MigrationLoader(connection)

            default_applied_migrations = copy(
                default_loader.applied_migrations)
            applied_migrations = copy(loader.applied_migrations)

            call_command('migrateproject', database='other', verbosity=0)

            default_loader = MigrationLoader(default_connection)
            loader = MigrationLoader(connection)

            # The default database should remain unchanged
            self.assertEqual(default_loader.applied_migrations,
                             default_applied_migrations)

            # The 'other' database should have been migrated
            self.assertNotEqual(loader.applied_migrations,
                                applied_migrations)

