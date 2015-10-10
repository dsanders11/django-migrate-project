from __future__ import unicode_literals

import os
import shutil

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase
from django.utils import six

from django_migrate_project.loader import PROJECT_MIGRATIONS_MODULE_NAME


MIGRATIONS_DIR = os.path.join(
    settings.BASE_DIR, PROJECT_MIGRATIONS_MODULE_NAME)

EXPECTED_MIGRATIONS = sorted([
    'event_calendar_0001_initial.py',
    'newspaper_0001_initial.py'
])


class MakeProjectMigrationsTest(TransactionTestCase):
    """ Tests for 'makeprojectmigrations' """

    def setUp(self):
        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)
        call_command('migrate', 'event_calendar', 'zero', verbosity=0)
        call_command('migrate', 'newspaper', 'zero', verbosity=0)

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

        call_command('migrate', 'event_calendar', 'zero', verbosity=0)
        call_command('migrate', 'newspaper', 'zero', verbosity=0)

    def get_migration_filenames(self, dir):
        """ Helper to get the filenames for migrations in a directory """

        filenames = []

        for filename in sorted(os.listdir(dir)):
            if not filename.endswith('.py'):
                continue
            elif filename != '__init__.py':
                filenames.append(filename)

        return filenames

    def test_success(self):
        """ Test succesfully creating project-level migrations """

        call_command('migrate', 'blog', verbosity=0)
        call_command('migrate', 'cookbook', verbosity=0)

        call_command('makeprojectmigrations', verbosity=0)
        self.assertEqual(self.get_migration_filenames(MIGRATIONS_DIR),
                         EXPECTED_MIGRATIONS)

    def test_unapplied_migrations(self):
        """ Test behavior if third-party apps have unapplied migrations """

        # Should behave the same as if the migrations are applied
        call_command('makeprojectmigrations', verbosity=0)
        self.assertEqual(self.get_migration_filenames(MIGRATIONS_DIR),
                         EXPECTED_MIGRATIONS)

    def test_bad_migrations_folder(self):
        """ Test error conditions with the project-level migrations folder """

        try:
            init_file = os.path.join(MIGRATIONS_DIR, '__init__.py')

            os.remove(init_file)

            with self.assertRaises(CommandError):
                call_command('makeprojectmigrations', verbosity=0)

            shutil.rmtree(MIGRATIONS_DIR)

            with self.assertRaises(CommandError):
                call_command('makeprojectmigrations', verbosity=0)
        finally:
            # Replace the files
            os.mkdir(MIGRATIONS_DIR)
            open(init_file, 'a').close()

    def test_dry_run(self):
        """ Test a dry-run of making the project-level migrations """

        out = six.StringIO()

        call_command('makeprojectmigrations', dry_run=True, stdout=out,
                     verbosity=3)

        # Confirm the migration looks like we expect
        self.assertIn("name='event'", out.getvalue().lower())
        self.assertIn("name='article'", out.getvalue().lower())
        self.assertIn("createmodel", out.getvalue().lower())
        self.assertEqual(out.getvalue().count("class "), 2)

        # No migrations on disk
        self.assertEqual(self.get_migration_filenames(MIGRATIONS_DIR), [])

        out = six.StringIO()

        # Verbosity below 3 doesn't output the migrations content
        call_command('makeprojectmigrations', dry_run=True, stdout=out,
                     verbosity=2)

        # Confirm the migration looks like we expect
        self.assertIn("migrations for", out.getvalue().lower())
        self.assertNotIn("name='event'", out.getvalue().lower())
        self.assertNotIn("name='article'", out.getvalue().lower())
        self.assertNotIn("createmodel", out.getvalue().lower())
        self.assertEqual(out.getvalue().count("class "), 0)

        # No migrations on disk
        self.assertEqual(self.get_migration_filenames(MIGRATIONS_DIR), [])

    def test_no_migrations(self):
        """ Test running the command when no migrations are needed """

        out = six.StringIO()

        # Make the migrations succesfully
        self.test_success()

        # Now there should be nothing left to migrate
        call_command('makeprojectmigrations', stdout=out, verbosity=3)

        self.assertIn("no changes", out.getvalue().lower())

        migrations_files = self.get_migration_filenames(MIGRATIONS_DIR)

        self.assertEqual([x for x in migrations_files if x.endswith('.py')],
                         EXPECTED_MIGRATIONS)

    def test_project_migrations_setting(self):
        """ Test the behavior with various PROJECT_MIGRATIONS values """

        # No apps listed for project migrations
        with self.settings(PROJECT_MIGRATIONS=[]):
            out = six.StringIO()

            # Now the only to migrate should be 'newspaper'
            call_command('makeprojectmigrations', stdout=out, verbosity=3)

            self.assertIn("migrations for", out.getvalue().lower())
            self.assertIn("newspaper", out.getvalue().lower())

            self.assertEqual(self.get_migration_filenames(MIGRATIONS_DIR),
                             ['newspaper_0001_initial.py'])

        self.tearDown()
        self.setUp()

        # Setting missing all together
        with self.settings():
            del settings.PROJECT_MIGRATIONS

            out = six.StringIO()

            # Now the only to migrate should be 'newspaper'
            call_command('makeprojectmigrations', stdout=out, verbosity=3)

            self.assertIn("migrations for", out.getvalue().lower())
            self.assertIn("newspaper", out.getvalue().lower())

            self.assertEqual(self.get_migration_filenames(MIGRATIONS_DIR),
                             ['newspaper_0001_initial.py'])

    def test_monkey_patch(self):
        """ Test the behavior of the command when monkey patching apps """

        from django.contrib.auth.models import User

        # Monkey patch the email field to be required
        for field in User._meta.fields:
            if field.name == 'email':
                field.blank = False
                break

        try:
            call_command('makeprojectmigrations', verbosity=0)

            migrations_files = self.get_migration_filenames(MIGRATIONS_DIR)

            self.assertEqual(len(migrations_files), 3)
            self.assertEqual('event_calendar_0001_initial.py',
                             migrations_files[1])
            self.assertEqual('newspaper_0001_initial.py',
                             migrations_files[2])
            self.assertTrue(migrations_files[0].startswith('auth_'))
        finally:
            field.blank = True
