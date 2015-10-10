from __future__ import unicode_literals

from optparse import make_option

import os

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
from django.db.migrations.state import ProjectState

from django_migrate_project.loader import (
    ProjectMigrationLoader, PROJECT_MIGRATIONS_MODULE_NAME
)


# NOTE: Much of this code is borrowed and modified from the standard migrate
class Command(MigrateCommand):
    help = "Migrate a project using previously collected migrations."

    option_list = BaseCommand.option_list + (
        make_option("--unapply", action='store_true',  dest='unapply',
                    default=False, help="Unapply the migrations instead."),
        make_option("--noinput", action='store_false', dest='interactive',
                    default=True, help=("Tells Django to NOT prompt the user "
                                        "for input of any kind.")),
        make_option('--fake', action='store_true', dest='fake', default=False,
                    help=("Mark migrations as run without actually running "
                          "them")),
        make_option("--database", action='store', dest='database',
                    default=DEFAULT_DB_ALIAS,
                    help=("Nominates a database to synchronize. Defaults to "
                          "the \"default\" database.")),
    )
    args = ""

    def handle(self, *args, **options):
        self.verbosity = verbosity = options.get('verbosity')
        self.interactive = interactive = options.get('interactive')

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
        executor.loader = ProjectMigrationLoader(connection)

        targets = executor.loader.graph.leaf_nodes()

        if options.get('unapply'):
            targets = []

            # We only want to unapply the project migrations
            for key, migration in executor.loader.project_migrations.items():
                app_label, migration_name = key
                migration_found = False

                for dependency in migration.dependencies:
                    if dependency[0] == app_label:  # pragma: no branch
                        result = executor.loader.check_key(dependency,
                                                           app_label)
                        dependency = result or dependency

                        if (dependency[0], None) not in targets:  # pragma: nb
                            targets.append(dependency)
                        migration_found = True

                if not migration_found:
                    for target in list(targets):
                        if target[0] == app_label and target[1] is not None:
                            targets.remove(target)

                    targets.append((app_label, None))
        else:
            # Trim non-project migrations
            project_migration_keys = executor.loader.project_migrations.keys()

            for migration_key in list(targets):
                if migration_key not in project_migration_keys:
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
                        "  Run 'manage.py makeprojectmigrations' to make new "
                        "migrations, and then re-run "
                        "'manage.py migrateproject' to apply them."
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
