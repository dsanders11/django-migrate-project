from __future__ import unicode_literals

from importlib import import_module
from optparse import make_option

import os
import sys

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management.commands.migrate import Command as MigrateCommand
from django.core.management.sql import (
    emit_post_migrate_signal, emit_pre_migrate_signal,
)
from django.db import connections, DEFAULT_DB_ALIAS
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState

from django_migrate_project.management.commands.migrateproject import ProjectMigrationLoader


class PendingMigrationLoader(ProjectMigrationLoader):
    def __init__(self, *args, **kwargs):
        self.pending_migrations_dir = kwargs.pop('pending_migrations_dir')

        super(PendingMigrationLoader, self).__init__(*args, **kwargs)

    def load_disk(self):
        """ Loads the migrations for the project from disk. """

        super(PendingMigrationLoader, self).load_disk()
        all_migrations = self.disk_migrations

        self.project_migrations = {}
        self.disk_migrations = {}
        self.unmigrated_apps = set()
        self.migrated_apps = set()

        migrations_dir = self.pending_migrations_dir
        migrations = [f for f in os.listdir(migrations_dir) if os.path.isfile(os.path.join(migrations_dir, f))]

        # Populate the dependencies so the graph is complete
        def populate_dependencies(migration):
            for dep in migration.dependencies:
                # if dep[0] in self.unmigrated_apps:
                #     self.unmigrated_apps.remove(dep[0])
 
                self.migrated_apps.add(dep[0])

                try:
                    self.disk_migrations[dep] = all_migrations[dep]
                except KeyError:
                    if dep[1] == "__first__":
                        for app_migration in all_migrations.keys():
                            if app_migration[0] == dep[0]:
                                internal_deps = [d for d in all_migrations[app_migration].dependencies if d[0] == dep[0]]
                                if not internal_deps:
                                    self.disk_migrations[app_migration] = all_migrations[app_migration]
                                    populate_dependencies(all_migrations[app_migration])
                    else:
                        # Most likely is a dependency on a project migration
                        pass

                    continue

                populate_dependencies(all_migrations[dep])

        pending_migrations = []

        for app_config in apps.get_app_configs():
            app_label = app_config.label

            app_migration_files = [m.rstrip(".py") for m in migrations if m.startswith(app_label) and m.endswith(".py")]

            for migration_file in app_migration_files:
                migration_name = migration_file.lstrip(app_label)[1:]

                try:
                    sys.path.insert(0, migrations_dir)
                    module = import_module(migration_file)
                except ImportError:
                #     if app_label not in self.migrated_apps:
                #         self.unmigrated_apps.add(app_label)
                    continue
                finally:
                    sys.path.pop(0)

                self.migrated_apps.add(app_label)

                migration = module.Migration(migration_name, app_label)
                self.disk_migrations[app_label, migration_name] = migration
                self.project_migrations[app_label, migration_name] = migration
                pending_migrations.append(migration)

        for migration in pending_migrations:
            populate_dependencies(migration)


# NOTE: Much of this code is borrowed and modified from the standard migrate
class Command(MigrateCommand):
    help = "Migrate a project using previously collected migrations."

    option_list = BaseCommand.option_list + (
        make_option("--unapply", action='store_true',  dest='unapply',
                    default=False, help="Unapply the migrations instead."),
        make_option("--input-dir", action='store', dest='input_dir',
                    default=None, help=("Directory to load the project "
                                        "migrations from.")),
        make_option("--noinput", action='store_false', dest='interactive',
                    default=True, help=("Tells Django to NOT prompt the user "
                                        "for input of any kind.")),
        make_option('--fake', action='store_true', dest='fake', default=False,
            help='Mark migrations as run without actually running them'),
        make_option("--database", action='store', dest='database',
                    default=DEFAULT_DB_ALIAS,
                    help=("Nominates a database to synchronize. Defaults to "
                          "the \"default\" database.")),
    )
    args = ""

    def handle(self, *args, **options):
        self.verbosity = verbosity = options.get('verbosity')
        self.interactive = interactive = options.get('interactive')
        migrations_dir = options.get('input_dir')

        try:
            default_input_dir = os.path.join(settings.BASE_DIR, 'pending_migrations')
        except AttributeError:
            default_input_dir = None

        if migrations_dir is None:
            if not default_input_dir:
                raise CommandError(
                    "No input directory to read migrations from. Either set "
                    "BASE_DIR in your settings or provide a directory path "
                    "via the --input-dir option.")
            else:
                migrations_dir = default_input_dir
        elif not migrations_dir:
            raise CommandError(
                "Provide a real directory path via the --input-dir option.")

        if not (os.path.exists(migrations_dir) and os.listdir(migrations_dir)):
            raise CommandError("Input directory (%s) doesn't exist or is "
                               "empty." % migrations_dir)

        # Get the database we're operating from
        db = options.get('database')
        connection = connections[db]

        # Hook for backends needing any database preparation
        try:
            connection.prepare_database()
        except AttributeError:  # pragma: no cover
            pass

        executor = MigrationExecutor(connection,
                                     self.migration_progress_callback)

        # Replace the loader with a project-level one
        executor.loader = PendingMigrationLoader(
            connection, pending_migrations_dir=migrations_dir)

        targets = executor.loader.graph.leaf_nodes()

        if options.get('unapply'):
            targets = []

            # We only want to unapply the project migrations
            for key, migration in executor.loader.project_migrations.items():
                app_label, migration_name = key
                migration_found = False

                for dependency in migration.dependencies:
                    if dependency[0] == app_label:
                        targets.append(dependency)
                        migration_found = True

                if not migration_found:
                    targets.append((app_label, None))
        else:
            # Trim non-project migrations
            for migration_key in list(targets):
                if not migration_key in executor.loader.project_migrations.keys():
                    targets.remove(migration_key)

        plan = executor.migration_plan(targets)

        MIGRATE_HEADING = self.style.MIGRATE_HEADING
        MIGRATE_LABEL = self.style.MIGRATE_LABEL

        # Print some useful info
        if verbosity > 0:
            self.stdout.write(MIGRATE_HEADING("Operations to perform:"))

            for target in targets:
                if target[1] is None:
                    self.stdout.write(MIGRATE_LABEL(
                        "  Unapply all migrations: ") + "%s" % (target[0],)
                    )
                else:
                    self.stdout.write(MIGRATE_LABEL(
                        "  Target specific migration: ") + "%s, from %s"
                        % (target[1], target[0])
                    )

        try:  # pragma: no cover
            emit_pre_migrate_signal([], verbosity, interactive,
                                    connection.alias)
        except TypeError:  # pragma: no cover
            emit_pre_migrate_signal(verbosity, interactive, connection.alias)

        # Migrate!
        if verbosity > 0:
            self.stdout.write(MIGRATE_HEADING("Running migrations:"))

        if not plan:
            if verbosity > 0:
                self.stdout.write("  No migrations to apply.")
                # If there's changes not in migrations, tell them how to fix it
                autodetector = MigrationAutodetector(
                    executor.loader.project_state(),
                    ProjectState.from_apps(apps),
                )
                changes = autodetector.changes(graph=executor.loader.graph)
                if changes:
                    self.stdout.write(self.style.NOTICE(
                        "  Your models have changes that are not yet reflected"
                        " in a migration, and so won't be applied."
                    ))
                    self.stdout.write(self.style.NOTICE(
                        "  Run 'manage.py makemigrations' to make new "
                        "migrations, and then re-run 'manage.py migrate' to "
                        "apply them."
                    ))
        else:
            executor.migrate(targets, plan, fake=options.get("fake", False))

        # Send the post_migrate signal, so individual apps can do whatever they
        # need to do at this point.
        try:  # pragma: no cover
            emit_post_migrate_signal([], verbosity, interactive,
                                     connection.alias)
        except TypeError:  # pragma: no cover
            emit_post_migrate_signal(verbosity, interactive, connection.alias)
