from __future__ import unicode_literals

from collections import defaultdict
from copy import copy
from optparse import make_option

import os
import shutil

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.migrations import Migration
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.optimizer import MigrationOptimizer
from django.db.migrations.writer import MigrationWriter


class Command(BaseCommand):
    help = "Collect the pending migrations for the project."

    option_list = BaseCommand.option_list + (
        make_option("--no-optimize", action='store_true', dest='no_optimize',
                    default=False, help=("Do not try to optimize the squashed "
                                         "operations.")),
        make_option("--output-dir", action='store', dest='output_dir',
                    default=None, help=("Directory to output the collected "
                                        "migrations to.")),
        make_option("--database", action='store', dest='database',
                    default=DEFAULT_DB_ALIAS,
                    help=("Nominates a database to synchronize. Defaults to "
                          "the \"default\" database.")),
    )
    args = ""

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')
        self.no_optimize = options.get('no_optimize')
        migrations_dir = options.get('output_dir')

        try:
            default_output_dir = os.path.join(settings.BASE_DIR, 'migrations')
        except AttributeError:
            default_output_dir = None

        if migrations_dir is None:
            if not default_output_dir:
                raise CommandError(
                    "No output directory to collect migrations to. Either set "
                    "BASE_DIR in your settings or provide a directory path "
                    "via the --output-dir option.")
            else:
                migrations_dir = default_output_dir
        elif not migrations_dir:
            raise CommandError(
                "Provide a real directory path via the --output-dir option.")

        db = options.get('database')
        connection = connections[db]

        MIGRATE_HEADING = self.style.MIGRATE_HEADING
        MIGRATE_LABEL = self.style.MIGRATE_LABEL

        if self.verbosity > 0:
            apps_with_models = []

            for app_config in apps.get_app_configs():
                if app_config.models_module is not None:
                    apps_with_models.append(app_config.label)

            app_list = ", ".join(sorted(apps_with_models))

            self.stdout.write(MIGRATE_HEADING("Operations to perform:"))
            self.stdout.write(
                MIGRATE_LABEL("  Collect all migrations: ") + app_list
            )

        loader = MigrationLoader(connection, ignore_no_migrations=True)
        app_migrations = defaultdict(list)

        # Check for conflicts
        conflicts = loader.detect_conflicts()
        if conflicts:
            name_str = "; ".join(
                "%s in %s" % (", ".join(names), app)
                for app, names in conflicts.items()
            )
            raise CommandError(
                "Conflicting migrations detected (%s).\nTo fix them run "
                "'python manage.py makemigrations --merge'" % name_str
            )

        # Only collect migrations that haven't been applied
        # NOTE: It's very important to keep the migrations sorted here,
        #       otherwise they may get out of order and the optimizer goes
        #       all out of whack because it's not good at out of order items
        for migration_key, migration in sorted(loader.disk_migrations.items()):
            if migration_key not in loader.applied_migrations:
                app_label, migration_name = migration_key
                app_migrations[app_label].append(migration)

        if self.verbosity > 0:
            self.stdout.write(MIGRATE_HEADING("Collecting migrations:"))

            for app in sorted(apps_with_models):
                write = self.stdout.write

                if app in app_migrations:
                    write("  Migrations collected for app '%s'" % app)
                else:
                    write("  No unapplied migrations for app '%s'" % app)

        # No migrations to bundle up, so return early
        if not app_migrations:
            return

        try:
            # Delete the output dir to avoid a combination of new and old files
            if os.path.exists(migrations_dir):
                shutil.rmtree(migrations_dir)

            os.mkdir(migrations_dir)

            project_migrations = {}

            # Create migrations for each individual app
            for app_label in app_migrations:
                migration_filename = app_label + '_migrations.py'
                project_migrations[app_label] = self.create_app_migration(
                    app_label, app_migrations[app_label])

            # Resolve dependencies between the consolidated migrations and save
            for app_label, migration in project_migrations.items():
                for dependency in copy(migration.dependencies):
                    # If cross-app dependency
                    if dependency[0] != app_label:
                        # And there is a project level migration for that app
                        if dependency[0] in project_migrations:
                            other_migration = project_migrations[dependency[0]]

                            # And the dependency is a replaced migration
                            if dependency in other_migration.replaces:
                                migration.dependencies.remove(dependency)
                                migration.dependencies.append(
                                    (dependency[0], 'project_migration'))

                # Write the migration to disk
                migration_filename = app_label + '_migrations.py'
                file_path = os.path.join(migrations_dir, migration_filename)
                writer = MigrationWriter(migration)

                with open(file_path, 'wb') as output_file:
                    output_file.write(writer.as_string())  # pragma: no branch
        except:
            # Delete the output dir to avoid a combination of new and old files
            if os.path.exists(migrations_dir):
                shutil.rmtree(migrations_dir)

            raise

    def create_app_migration(self, app_label, migrations):
        """ Create a migration for the app which replaces the migrations """

        operations = []
        dependencies = set()
        replaces = set()

        # Create the list of migrations this one will replace
        for migration in migrations:
            replaces.add((migration.app_label, migration.name))

        # Gather up the operations to perform and find dependencies
        for migration in migrations:
            operations.extend(migration.operations)

            for dependency in migration.dependencies:
                different_app = (dependency[0] != migration.app_label)

                if different_app or dependency not in replaces:
                    dependencies.add(dependency)

        MIGRATE_HEADING = self.style.MIGRATE_HEADING

        if self.no_optimize:
            if self.verbosity > 0:
                self.stdout.write(MIGRATE_HEADING(
                    "(Skipping optimization for '" + app_label + "'.)"))
            new_operations = operations
        else:
            if self.verbosity > 0:
                self.stdout.write(MIGRATE_HEADING(
                    "Optimizing '" + app_label + "'..."))

            optimizer = MigrationOptimizer()
            new_operations = optimizer.optimize(operations, app_label)

            if self.verbosity > 0:
                if len(new_operations) == len(operations):
                    self.stdout.write("  No optimizations possible.")
                else:
                    self.stdout.write(
                        "  Optimized from %s operations to %s operations." %
                        (len(operations), len(new_operations))
                    )

        # Make a new migration class with these operations
        migration_class = type(str('Migration'), (Migration, ), {
            'dependencies': dependencies,
            'operations': new_operations,
            'replaces': sorted(replaces),
        })

        return migration_class('project_migration', app_label)
