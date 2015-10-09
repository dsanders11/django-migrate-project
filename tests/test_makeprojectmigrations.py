from __future__ import unicode_literals

from imp import load_source
from os.path import exists as path_exists
from unittest import skip

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

import django

import mock


MIGRATIONS_DIR = os.path.join(settings.BASE_DIR, 'migrations')

class MakeProjectMigrationsTest(TransactionTestCase):
    """ Tests for 'makeprojectmigrations' """

    def setUp(self):
        # Roll back migrations to a blank state
        call_command('migrate', 'blog', 'zero', verbosity=0)
        call_command('migrate', 'cookbook', 'zero', verbosity=0)

    def tearDown(self):
        # Delete any created migrations
        try:
            for filename in os.listdir(MIGRATIONS_DIR):
                if filename != '__init__.py':
                    os.remove(os.path.join(MIGRATIONS_DIR, filename))
        except IOError:
            pass

        try:
            call_command('migrate', 'calendar', 'zero', verbosity=0)
        except CommandError:
            pass

    def test_success(self):
        """ Test succesfully creating project-level migrations """

        call_command('migrate', 'blog', verbosity=0)
        call_command('migrate', 'cookbook', verbosity=0)

        call_command('makeprojectmigrations', verbosity=0)
        self.assertEqual(sorted(os.listdir(MIGRATIONS_DIR)),
            sorted(['__init__.py', 'event_calendar_0001_initial.py']))

    def test_unapplied_migrations(self):
        """ Test behavior if third-party apps have unapplied migrations """

        # Should behave the same as if the migrations are applied
        call_command('makeprojectmigrations', verbosity=0)
        self.assertEqual(sorted(os.listdir(MIGRATIONS_DIR)),
            sorted(['__init__.py', 'event_calendar_0001_initial.py']))

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
        self.assertIn("createmodel", out.getvalue().lower())
        self.assertEqual(out.getvalue().count("class "), 1)

        # No migrations on disk
        self.assertEqual(os.listdir(MIGRATIONS_DIR), ['__init__.py'])         

    def test_no_migrations(self):
        """ Test running the command when no migrations are needed """

        out = six.StringIO()

        # Make the migrations succesfully
        self.test_success()

        # Now there should be nothing left to migrate
        call_command('makeprojectmigrations', stdout=out, verbosity=3)

        self.assertIn("no changes", out.getvalue().lower())

        migrations_files = sorted(os.listdir(MIGRATIONS_DIR))

        self.assertEqual([x for x in migrations_files if x.endswith('.py')],
            sorted(['__init__.py', 'event_calendar_0001_initial.py']))

    def test_project_migrations_setting(self):
        """ Test the behavior with various PROJECT_MIGRATIONS values """

        # No apps listed for project migrations
        with self.settings(PROJECT_MIGRATIONS=[]):
            out = six.StringIO()

            # Now there should be nothing to migrate
            call_command('makeprojectmigrations', stdout=out, verbosity=3)

            self.assertIn("no changes", out.getvalue().lower())

            migrations_files = sorted(os.listdir(MIGRATIONS_DIR))

            self.assertEqual(os.listdir(MIGRATIONS_DIR), ['__init__.py'])

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

            migrations_files = sorted(os.listdir(MIGRATIONS_DIR))

            self.assertEqual(len(migrations_files), 3)
            self.assertEqual('__init__.py', migrations_files[0])
            self.assertEqual('event_calendar_0001_initial.py',
                             migrations_files[2])
            self.assertTrue(migrations_files[1].startswith('auth_'))
        finally:
            field.blank = True
