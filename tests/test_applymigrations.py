from __future__ import unicode_literals

from copy import copy

import os
import shutil
import sys
import tempfile

from django.apps import apps
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.migrations.loader import MigrationLoader
from django.db.models.signals import post_migrate, pre_migrate
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings, TransactionTestCase
from django.utils import six

import mock


TEST_MIGRATIONS_DIR = os.path.join(settings.BASE_DIR, 'test_migrations')
INITIAL_MIGRATION_DIR = os.path.join(TEST_MIGRATIONS_DIR, 'initial_migration')
ROUTINE_MIGRATION_DIR = os.path.join(TEST_MIGRATIONS_DIR, 'routine_migration')
UNOPTIMIZED_MIGRATION_DIR = os.path.join(
    TEST_MIGRATIONS_DIR, 'unoptimized_initial_migration')
DEPENDENCY_EDGE_MIGRATION_DIR = os.path.join(
    TEST_MIGRATIONS_DIR, 'dependency_edge_case')


class ApplyMigrationsTest(TransactionTestCase):
    """ Tests for 'applymigrations' """

    def setUp(self):
        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)

    def tearDown(self):
        self.clear_migrations_modules()

    def clear_migrations_modules(self):
        # Destroy modules that were loaded for migrations
        sys.modules.pop("blog_0001_project", None)
        sys.modules.pop("cookbook_0001_project", None)

    def test_unapply(self):
        """ Test unapplying an applied project migration """

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = copy(loader.applied_migrations)

        # Applied via applymigrations and then unapplied
        call_command('applymigrations', input_dir=INITIAL_MIGRATION_DIR,
                     verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        self.assertNotEqual(loader.applied_migrations, applied_migrations)

        out = six.StringIO()
        call_command('applymigrations', unapply=True, stdout=out, verbosity=1,
                     input_dir=INITIAL_MIGRATION_DIR)

        # Check that it sas it was unapplied
        self.assertIn("unapply all", out.getvalue().lower())

        # Check that database is back to original
        loader = MigrationLoader(connection)
        self.assertEqual(loader.applied_migrations, applied_migrations)

        ####
        # Non-initial migration

        self.clear_migrations_modules()

        # Partial migration to set state
        call_command('migrate', 'blog', '0001', verbosity=0)
        call_command('migrate', 'cookbook', '0003', verbosity=0)

        loader = MigrationLoader(connection)
        applied_migrations = copy(loader.applied_migrations)

        # Applied via applymigrations and then unapplied
        call_command('applymigrations', input_dir=ROUTINE_MIGRATION_DIR,
                     verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        self.assertNotEqual(loader.applied_migrations, applied_migrations)

        out = six.StringIO()
        call_command('applymigrations', unapply=True, stdout=out, verbosity=1,
                     input_dir=ROUTINE_MIGRATION_DIR)

        # Check that they were unapplied
        self.assertIn("unapplying blog", out.getvalue().lower())
        self.assertIn("unapplying cookbook", out.getvalue().lower())

        # Check that database is back to original
        loader = MigrationLoader(connection)
        self.assertEqual(loader.applied_migrations, applied_migrations)

    def test_nothing_to_apply(self):
        """ Test applying already applied project migration """

        # Applied via applymigrations and then again
        call_command('applymigrations', input_dir=INITIAL_MIGRATION_DIR,
                     verbosity=0)

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = copy(loader.applied_migrations)

        out = six.StringIO()
        call_command('applymigrations', stdout=out, verbosity=1,
                     input_dir=INITIAL_MIGRATION_DIR)

        # Check that it says nothing was applied
        self.assertIn("no migrations", out.getvalue().lower())

        # Check that database stayed the same
        loader = MigrationLoader(connection)
        self.assertEqual(loader.applied_migrations, applied_migrations)

        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)

        # Applied via migrate and then again applymigrations
        call_command('migrate', verbosity=0)

        loader = MigrationLoader(connection)
        applied_migrations = copy(loader.applied_migrations)

        out = six.StringIO()
        call_command('applymigrations', stdout=out, verbosity=1,
                     input_dir=INITIAL_MIGRATION_DIR)

        # Check that it says nothing was applied
        self.assertIn("no migrations", out.getvalue().lower())

        # Check that database stayed the same
        loader = MigrationLoader(connection)
        self.assertEqual(loader.applied_migrations, applied_migrations)

        # One more time, with no verbosity for full branch coverage
        call_command('applymigrations', verbosity=0,
                     input_dir=INITIAL_MIGRATION_DIR)

    def test_human_output(self):
        """ Test the human visible output of the migration """

        out = six.StringIO()
        call_command('applymigrations', stdout=out, verbosity=1,
                     input_dir=INITIAL_MIGRATION_DIR)

        self.assertIn("running", out.getvalue().lower())
        self.assertIn("target", out.getvalue().lower())

    def test_dependency_edge_case(self):
        """ Test an edge case where migration dependency is fully migrated """

        # Fully migrate the app the project migration depends on
        call_command('migrate', 'cookbook', verbosity=0)

        module = 'django_migrate_project.management.commands.applymigrations'
        get_app_configs_path = module + '.apps.get_app_configs'

        app_configs = apps.get_app_configs()

        with mock.patch(get_app_configs_path) as get_app_configs:
            # NOTE: This is reversed to get full line statement coverage,
            #       where it needs 'cookbook' to be processed before 'blog'
            get_app_configs.return_value = list(reversed(list(app_configs)))

            connection = connections[DEFAULT_DB_ALIAS]
            loader = MigrationLoader(connection)
            applied_migrations = copy(loader.applied_migrations)

            call_command('applymigrations', verbosity=0,
                         input_dir=DEPENDENCY_EDGE_MIGRATION_DIR)

            # Check that database changed
            loader = MigrationLoader(connection)
            self.assertNotEqual(loader.applied_migrations, applied_migrations)

    def test_signals(self):
        """ Test the signals emitted during the migration """

        app_config = apps.get_app_config('blog')

        pre_migrate_callback = mock.MagicMock()
        post_migrate_callback = mock.MagicMock()

        pre_migrate.connect(pre_migrate_callback, sender=app_config)
        post_migrate.connect(post_migrate_callback, sender=app_config)

        self.test_unapply()
        self.test_nothing_to_apply()
        self.test_routine_migration()

        self.assertEqual(pre_migrate_callback.call_count, 16)
        self.assertEqual(post_migrate_callback.call_count, 16)

    def test_changes_detected(self):
        """ Test a migration with model changes detected """

        # Migrate first, so that no migrations are available to apply
        call_command('applymigrations', verbosity=0,
                     input_dir=INITIAL_MIGRATION_DIR)

        module = 'django_migrate_project.management.commands.applymigrations'
        changes_path = module + '.MigrationAutodetector.changes'

        with mock.patch(changes_path) as changes:
            changes.return_value = True

            out = six.StringIO()
            call_command('applymigrations', stdout=out, verbosity=1,
                         input_dir=INITIAL_MIGRATION_DIR)

            self.assertIn("have changes", out.getvalue().lower())
            self.assertIn("makemigrations", out.getvalue().lower())

    def test_routine_migration(self):
        """ Test a non-initial project migration """

        # Partial migration to set state
        call_command('migrate', 'blog', '0001', verbosity=0)
        call_command('migrate', 'cookbook', '0003', verbosity=0)

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = copy(loader.applied_migrations)

        call_command('applymigrations', input_dir=ROUTINE_MIGRATION_DIR,
                     verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        self.assertNotEqual(loader.applied_migrations, applied_migrations)

    def test_unoptimized_migration(self):
        """ Test an unoptimized project migration """

        connection = connections[DEFAULT_DB_ALIAS]
        loader = MigrationLoader(connection)
        applied_migrations = copy(loader.applied_migrations)

        call_command('applymigrations', input_dir=UNOPTIMIZED_MIGRATION_DIR,
                     verbosity=0)

        # Check that database changed
        loader = MigrationLoader(connection)
        self.assertNotEqual(loader.applied_migrations, applied_migrations)

    def test_input_dir_error(self):
        """ Test running the management command with bad input dir option """

        with self.assertRaises(CommandError):
            call_command('applymigrations', input_dir="", verbosity=0)

        try:
            base_dir = tempfile.mkdtemp()
            dir = os.path.join(base_dir, 'foo')

            # Non-existent dir
            with self.assertRaises(CommandError):
                call_command('applymigrations', input_dir=dir, verbosity=0)

            # Empty dir
            with self.assertRaises(CommandError):
                call_command('applymigrations', input_dir=base_dir, verbosity=0)
        finally:
            shutil.rmtree(base_dir)

        with override_settings():
            del settings.BASE_DIR  # Simulate it not being set in settings

            with self.assertRaises(CommandError):
                call_command('applymigrations', verbosity=0)

    @override_settings(BASE_DIR=tempfile.mkdtemp())
    def test_default_dir(self):
        """ Test migrating a project using files from the default dir """

        try:
            shutil.copytree(INITIAL_MIGRATION_DIR,
                            os.path.join(settings.BASE_DIR, 'pending_migrations'))

            connection = connections[DEFAULT_DB_ALIAS]
            loader = MigrationLoader(connection)
            applied_migrations = copy(loader.applied_migrations)

            call_command('applymigrations', verbosity=0)

            loader = MigrationLoader(connection)

            # Check that database was migrated
            self.assertNotEqual(loader.applied_migrations, applied_migrations)
        finally:
            shutil.rmtree(settings.BASE_DIR)

    def test_alt_database(self):
        """ Test migrating a project with an alternate database selected """

        # Roll back migrations to a blank state in the 'other' database
        call_command('migrate', 'blog', 'zero', database='other', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', database='other',
                     verbosity=0)

        default_connection = connections[DEFAULT_DB_ALIAS]
        connection = connections['other']

        default_loader = MigrationLoader(default_connection)
        loader = MigrationLoader(connection)

        default_applied_migrations = copy(default_loader.applied_migrations)
        applied_migrations = copy(loader.applied_migrations)

        call_command('applymigrations', database='other', verbosity=0,
                     input_dir=INITIAL_MIGRATION_DIR)

        default_loader = MigrationLoader(default_connection)
        loader = MigrationLoader(connection)

        # The default database should remain unchanged
        self.assertEqual(default_loader.applied_migrations,
                         default_applied_migrations)

        # The 'other' database should have been migrated
        self.assertNotEqual(loader.applied_migrations,
                            applied_migrations)
