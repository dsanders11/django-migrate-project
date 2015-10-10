from __future__ import unicode_literals

import os
from optparse import make_option

from django.core.management.commands.makemigrations import (
    Command as MakeMigrationsCommand)

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.migrations.writer import MigrationWriter

from django_migrate_project.loader import (
    ProjectMigrationLoader, PROJECT_MIGRATIONS_MODULE_NAME
)
from django_migrate_project.questioner import (
    ProjectInteractiveMigrationQuestioner)


# Monkey patch to avoid duplicating code
import django

makemigrations = django.core.management.commands.makemigrations

makemigrations.MigrationLoader = ProjectMigrationLoader
makemigrations.InteractiveMigrationQuestioner = \
    ProjectInteractiveMigrationQuestioner


class Command(MakeMigrationsCommand):
    help = "Creates new migration(s) for a project."

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true', dest='dry_run',
                    default=False, help=("Just show what migrations would be "
                                         "made; don't actually write them.")),
        make_option('--noinput', action='store_false', dest='interactive',
                    default=True, help=("Tells Django to NOT prompt the user "
                                        "for input of any kind.")),
    )

    args = ""

    def handle(self, *app_labels, **options):
        migrations_dir = os.path.join(
            settings.BASE_DIR, PROJECT_MIGRATIONS_MODULE_NAME)

        if not os.path.exists(migrations_dir):
            raise CommandError(
                "No migrations found, project migrations folder '(%s)' "
                "doesn't exist." % migrations_dir)
        elif not os.path.exists(os.path.join(migrations_dir, "__init__.py")):
            raise CommandError(
                "Project migrations folder '(%s)' missing '__init__.py' "
                "file." % migrations_dir)

        super(Command, self).handle(*app_labels, **options)

    def write_migration_files(self, changes):
        """ Takes a changes dict and writes them out as migration files. """

        MIGRATE_HEADING = self.style.MIGRATE_HEADING
        MIGRATE_LABEL = self.style.MIGRATE_LABEL
        write = self.stdout.write

        migrations_dir = os.path.join(
            settings.BASE_DIR, PROJECT_MIGRATIONS_MODULE_NAME)

        for app_label, app_migrations in changes.items():
            if self.verbosity >= 1:
                write(MIGRATE_HEADING(
                    "Migrations for '%s':" % app_label) + "\n"
                )
            for migration in app_migrations:
                # Describe the migration
                writer = MigrationWriter(migration)
                migration_name = app_label + "_" + writer.filename
                filename = os.path.join(migrations_dir, migration_name)

                if self.verbosity >= 1:
                    write("  %s:\n" % (MIGRATE_LABEL(migration_name),))
                    for operation in migration.operations:
                        write("    - %s\n" % operation.describe())
                if not self.dry_run:
                    # Write the migrations file to the disk.
                    migration_string = writer.as_string()
                    with open(filename, "wb") as fh:
                        fh.write(migration_string)
                elif self.verbosity == 3:
                    # Alternatively, makemigrations --dry-run --verbosity 3
                    # will output the migrations to stdout rather than saving
                    # the file to the disk.
                    write(MIGRATE_HEADING(
                        "Full migrations file '%s':" % migration_name) + "\n"
                    )
                    write("%s\n" % writer.as_string())
