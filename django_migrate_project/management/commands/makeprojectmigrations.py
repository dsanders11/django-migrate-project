from __future__ import unicode_literals

import os
import sys
from itertools import takewhile
from importlib import import_module
from optparse import make_option

from django.core.management.commands.makemigrations import Command as MakeMigrationsCommand

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.migrations import Migration
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import (
    InteractiveMigrationQuestioner, MigrationQuestioner,
)
from django.db.migrations.state import ProjectState
from django.db.migrations.writer import MigrationWriter
from django.utils.six import iteritems
from django.utils.six.moves import zip

import django

class ProjectMigrationLoader(MigrationLoader):
    def load_disk(self):
        """ Loads the migrations for the project from disk. """

        super(ProjectMigrationLoader, self).load_disk()

        self.unmigrated_apps = set(self.unmigrated_apps)
        self.migrated_apps = set(self.migrated_apps)

        migrations_dir = "migrations"
        migrations = [f for f in os.listdir(migrations_dir) if os.path.isfile(os.path.join(migrations_dir, f))]

        for app_config in apps.get_app_configs():
            app_label = app_config.label

            app_migration_files = [m.rstrip(".py") for m in migrations if m.startswith(app_label) and m.endswith(".py")]

            for migration_file in app_migration_files:
                migration_name = migration_file.lstrip(app_label)[1:]

                try:
                    sys.path.insert(0, migrations_dir)
                    module = import_module(migration_file)
                except ImportError:
                    continue
                finally:
                    sys.path.pop(0)

                self.migrated_apps.add(app_label)
                self.unmigrated_apps.discard(app_label)

                migration = module.Migration(migration_name, app_label)
                self.disk_migrations[app_label, migration_name] = migration

        for app_label in self.unmigrated_apps:
            self.migrated_apps.add(app_label)

        self.unmigrated_apps = []


class ProjectMigrationQuestioner(InteractiveMigrationQuestioner):
    def ask_initial(self, app_label):
        try:
            project_migrations = settings.PROJECT_MIGRATIONS
        except AttributeError:
            project_migrations = []

        if app_label in project_migrations:
            return True
        else:
            return super(ProjectMigrationQuestioner, self).ask_initial(app_label)


# Monkey patch
django.core.management.commands.makemigrations.MigrationLoader = ProjectMigrationLoader
django.core.management.commands.makemigrations.InteractiveMigrationQuestioner = ProjectMigrationQuestioner


class Command(MakeMigrationsCommand):
    help = "Creates new migration(s) for a project."

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true', dest='dry_run', default=False,
            help="Just show what migrations would be made; don't actually write them."),
        make_option('--empty', action='store_true', dest='empty', default=False,
            help="Create an empty migration."),
        make_option('--noinput', action='store_false', dest='interactive', default=True,
            help='Tells Django to NOT prompt the user for input of any kind.'),
    )

    args = ""

    def write_migration_files(self, changes):
        """
        Takes a changes dict and writes them out as migration files.
        """
        for app_label, app_migrations in changes.items():
            if self.verbosity >= 1:
                self.stdout.write(self.style.MIGRATE_HEADING("Migrations for '%s':" % app_label) + "\n")
            for migration in app_migrations:
                # Describe the migration
                writer = MigrationWriter(migration)
                migration_filename = app_label + "_" + writer.filename
                if self.verbosity >= 1:
                    self.stdout.write("  %s:\n" % (self.style.MIGRATE_LABEL(migration_filename),))
                    for operation in migration.operations:
                        self.stdout.write("    - %s\n" % operation.describe())
                if not self.dry_run:
                    # Write the migrations file to the disk.
                    migrations_directory = os.path.join(settings.BASE_DIR, 'migrations')
                    filename = os.path.basename(writer.path)
                    migration_string = writer.as_string()
                    with open(os.path.join(migrations_directory, migration_filename), "wb") as fh:
                        fh.write(migration_string)
                elif self.verbosity == 3:
                    # Alternatively, makemigrations --dry-run --verbosity 3
                    # will output the migrations to stdout rather than saving
                    # the file to the disk.
                    self.stdout.write(self.style.MIGRATE_HEADING(
                        "Full migrations file '%s':" % migration_filename) + "\n"
                    )
                    self.stdout.write("%s\n" % writer.as_string())
