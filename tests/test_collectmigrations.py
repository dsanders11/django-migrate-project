from __future__ import unicode_literals

from imp import load_source
from os.path import exists as path_exists

# Python 3 compatibility
try:
    import __builtin__ as builtins
except ImportError:
    import builtins

import os
import shutil
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings, TransactionTestCase
from django.utils import six

import mock


BLOG_FULL_MIGRATION_OPERATION_COUNT = 2
COOKBOOK_FULL_MIGRATION_OPERATION_COUNT = 8
COOKBOOK_UNOPTIMIZED_FULL_MIGRATION_OPERATION_COUNT = 11

DEFAULT_DIR = os.path.join(settings.BASE_DIR, 'pending_migrations')


class CollectMigrationsTest(TransactionTestCase):
    """ Tests for 'collectmigrations' """

    def setUp(self):
        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)

    def tearDown(self):
        # Delete the default migrations path if it exists
        if path_exists(DEFAULT_DIR):
            shutil.rmtree(DEFAULT_DIR)

    def load_migrations(self, dir=DEFAULT_DIR):
        """ Load migration source files from disk """

        blog_migrations = load_source(
            'blog_migrations', os.path.join(dir, 'blog_0001_project.py'))
        cookbook_migrations = load_source(
            'cookbook_migrations', os.path.join(dir, 'cookbook_0001_project.py'))

        return blog_migrations, cookbook_migrations

    def test_initial_collect(self):
        """ Test collecting migrations when test apps have none applied """

        custom_dir = os.path.join(tempfile.mkdtemp(), 'migrations')

        # Test outputting to both the default directory and a custom directory
        for output_dir in (DEFAULT_DIR, custom_dir):
            out = six.StringIO()

            try:
                if output_dir == custom_dir:
                    call_command('collectmigrations', stdout=out,
                                 output_dir=output_dir, verbosity=3)
                else:
                    call_command('collectmigrations', stdout=out, verbosity=3)

                self.assertTrue(path_exists(output_dir))
                blog_migrations, cookbook_migrations = self.load_migrations(
                    dir=output_dir)
            finally:
                # Clean up immediately to prevent dangling temp dirs
                if path_exists(output_dir):
                    shutil.rmtree(output_dir)

            # Check that the human visible output looks as expected
            self.assertIn("migrations collected", out.getvalue().lower())
            self.assertIn("optimizing", out.getvalue().lower())
            self.assertIn("optimized from", out.getvalue().lower())

            # Check that migrations have the correct number of operations
            self.assertEqual(len(blog_migrations.Migration.operations),
                             BLOG_FULL_MIGRATION_OPERATION_COUNT)
            self.assertEqual(len(cookbook_migrations.Migration.operations),
                             COOKBOOK_FULL_MIGRATION_OPERATION_COUNT)

            # Check the migration dependencies
            self.assertEqual(blog_migrations.Migration.dependencies,
                             [('cookbook', '0001_project')])
            self.assertEqual(cookbook_migrations.Migration.dependencies, [])

            # Check the migration replaces count
            self.assertEqual(len(blog_migrations.Migration.replaces), 2)
            self.assertEqual(len(cookbook_migrations.Migration.replaces), 5)

    def test_migration_needed(self):
        """ Test collecting migrations when apps need non-initial migration """

        # Migrate test apps part way
        call_command('migrate', 'blog', '0001', verbosity=0)
        call_command('migrate', 'cookbook', '0003', verbosity=0)

        out = six.StringIO()
        call_command('collectmigrations', stdout=out, verbosity=3)

        self.assertTrue(path_exists(DEFAULT_DIR))
        self.assertIn("no unapplied migrations", out.getvalue().lower())
        self.assertIn("migrations collected", out.getvalue().lower())

        blog_migrations, cookbook_migrations = self.load_migrations()

        # Check the migration dependencies
        self.assertEqual(blog_migrations.Migration.dependencies,
                         [('blog', '0001_initial')])
        self.assertEqual(cookbook_migrations.Migration.dependencies,
                         [('cookbook', '0003_auto_20150514_1515')])

        # Check the migration replaces count
        self.assertEqual(len(blog_migrations.Migration.replaces), 1)
        self.assertEqual(len(cookbook_migrations.Migration.replaces), 2)

    def test_single_app_migration(self):
        """ Test collecting migrations when a single app needs a migration """

        # Migrate 'cookbook' all the way so only 'blog' is unmigrated
        call_command('migrate', 'cookbook', verbosity=0)

        call_command('collectmigrations', verbosity=0)
        blog_migrations = os.path.join(DEFAULT_DIR, 'blog_0001_project.py')
        cookbook_migrations = os.path.join(
            DEFAULT_DIR, 'cookbook_0001_project.py')

        self.assertTrue(path_exists(DEFAULT_DIR))
        self.assertTrue(path_exists(blog_migrations))
        self.assertFalse(path_exists(cookbook_migrations))

    def test_path_exists(self):
        """ Test collecting migrations when a previous collection exists """

        custom_dir = os.path.join(tempfile.mkdtemp(), 'migrations')

        # Test outputting to both the default directory and a custom directory
        for output_dir in (DEFAULT_DIR, custom_dir):
            blog_migrations = os.path.join(output_dir, 'blog_0001_project.py')

            try:
                # Do a normal collection to fill the directory to start
                call_command('collectmigrations', output_dir=output_dir,
                             verbosity=0)
                self.assertTrue(path_exists(output_dir))
                self.assertTrue(path_exists(blog_migrations))

                # Fully migrate the 'blog' test app
                call_command('migrate', 'blog', verbosity=0)

                # Check that the directory looks as we expect, which means it
                # should have no file for the fully migrated 'blog' test app
                call_command('collectmigrations', output_dir=output_dir,
                             verbosity=0)
                self.assertTrue(path_exists(output_dir))
                self.assertFalse(path_exists(blog_migrations))
            finally:
                # Clean up immediately to prevent dangling temp dirs
                if path_exists(output_dir):
                    shutil.rmtree(output_dir)

            # Revert the migration of the 'blog' test app
            call_command('migrate', 'blog', 'zero', verbosity=0)

    def test_io_error(self):
        """ Test collecting migrations when an IOError occurs """

        with mock.patch.object(builtins, 'open') as mock_open:
            mock_open.side_effect = IOError()

            with self.assertRaises(IOError):
                call_command('collectmigrations', verbosity=0)

        self.assertFalse(path_exists(DEFAULT_DIR))

        module = 'django_migrate_project.management.commands.collectmigrations'
        mkdir_path = module + '.os.mkdir'

        with mock.patch(mkdir_path) as mkdir:
            mkdir.side_effect = IOError()

            with self.assertRaises(IOError):
                call_command('collectmigrations', verbosity=0)

        self.assertFalse(path_exists(DEFAULT_DIR))

    def test_output_dir_error(self):
        """ Test running the management command with bad output dir option """

        with self.assertRaises(CommandError):
            call_command('collectmigrations', output_dir="", verbosity=0)

        with override_settings():
            del settings.BASE_DIR  # Simulate it not being set in settings

            with self.assertRaises(CommandError):
                call_command('collectmigrations', verbosity=0)

    def test_nothing_to_collect(self):
        """ Test collecting migrations when everything has been applied """

        # Migrate test apps all the way forward
        call_command('migrate', 'blog', verbosity=0)
        call_command('migrate', 'cookbook', verbosity=0)

        # Default path case
        out = six.StringIO()
        call_command('collectmigrations', stdout=out, verbosity=3)

        self.assertFalse(path_exists(DEFAULT_DIR))
        self.assertIn("no unapplied migrations", out.getvalue().lower())
        self.assertNotIn("migrations collected", out.getvalue().lower())

    def test_no_optimize(self):
        """ Test collecting migrations with optimize turned off """

        out = six.StringIO()
        call_command('collectmigrations', no_optimize=True, stdout=out,
                     verbosity=3)

        self.assertTrue(path_exists(DEFAULT_DIR))
        self.assertIn("migrations collected", out.getvalue().lower())
        self.assertIn("skipping optimiz", out.getvalue().lower())
        self.assertNotIn("optimizing", out.getvalue().lower())

        blog_migrations, cookbook_migrations = self.load_migrations()

        # Check no optimization took place
        self.assertEqual(len(blog_migrations.Migration.operations),
                         BLOG_FULL_MIGRATION_OPERATION_COUNT)
        self.assertEqual(len(cookbook_migrations.Migration.operations),
                         COOKBOOK_UNOPTIMIZED_FULL_MIGRATION_OPERATION_COUNT)

        # One more time with no verbosity for full branch coverage
        call_command('collectmigrations', no_optimize=True, verbosity=0)

    def test_alt_database(self):
        """ Test collecting migrations with an alternate database selected """

        # Migrate test apps all the way forward on the default DB
        call_command('migrate', 'blog', verbosity=0)
        call_command('migrate', 'cookbook', verbosity=0)

        # Unapply all migrations on the other DB
        call_command('migrate', 'blog', 'zero', database='other', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', database='other',
                     verbosity=0)

        # Collect on the default DB to confirm nothing is collected
        out = six.StringIO()
        call_command('collectmigrations', stdout=out, verbosity=3)

        self.assertFalse(path_exists(DEFAULT_DIR))
        self.assertNotIn("migrations collected", out.getvalue().lower())
        self.assertNotIn("optimizing", out.getvalue().lower())

        # Collect on the other DB
        out = six.StringIO()
        call_command('collectmigrations', database='other', stdout=out,
                     verbosity=3)

        self.assertTrue(path_exists(DEFAULT_DIR))
        self.assertIn("migrations collected", out.getvalue().lower())
        self.assertIn("optimizing", out.getvalue().lower())

    def test_conflict(self):
        """ Test collecting migrations which causes a conflict """

        module = 'django_migrate_project.management.commands.collectmigrations'
        detect_conflicts_path = module + '.MigrationLoader.detect_conflicts'

        with mock.patch(detect_conflicts_path) as detect_conflicts:
            detect_conflicts.return_value = {
                'blog': ('0001_initial', '0002_tag')
            }

            with self.assertRaises(CommandError):
                call_command('collectmigrations', verbosity=0)

    def test_silent_collection(self):
        """ Test collecting migrations with verbosity set to silent """

        out = six.StringIO()
        call_command('collectmigrations', stdout=out, verbosity=0)

        self.assertFalse(out.getvalue())
