from __future__ import unicode_literals

from collections import defaultdict
from copy import copy
from itertools import combinations, takewhile
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

from django_migrate_project.management.commands.makeprojectmigrations import ProjectMigrationLoader


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

    def _make_name(self, idx):
        return "{0:04d}".format(idx + 1)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity')
        self.no_optimize = options.get('no_optimize')
        migrations_dir = options.get('output_dir')

        try:
            default_output_dir = os.path.join(settings.BASE_DIR, 'pending_migrations')
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

        loader = ProjectMigrationLoader(connection, ignore_no_migrations=True)
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

        def list_of_lists():
            result_list = []
            result_list.append([])

            return result_list

        leaf_nodes = loader.graph.leaf_nodes()
        new_app_migrations = defaultdict(list_of_lists)
        new_app_leaf_migrations = {}

        # NOTE: Grabbed from Django mainline and modified
        def _find_common_ancestors(nodes):
            # Grab out the migrations in question, and work out their
            # common ancestor.
            migrations = []
            for app_label, migration_name in nodes:
                migration = loader.get_migration(app_label, migration_name)
                migration.ancestry = [node for node in loader.graph.forwards_plan((app_label, migration_name)) if node not in loader.applied_migrations and node not in leaf_nodes]
                migrations.append(migration)
            all_items_equal = lambda seq: all(item == seq[0] for item in seq[1:])
            migrations_generations = zip(*[m.ancestry for m in migrations])
            common_ancestors = takewhile(all_items_equal, migrations_generations)
            return list(common_ancestors)

        def walk_nodes(current_app, migration_key):
            if migration_key not in loader.applied_migrations:
                app_label, migration_name = migration_key
                migration = loader.disk_migrations[migration_key]

                if app_label == current_app and migration not in new_app_migrations[app_label][0]:
                    new_app_migrations[app_label][0].append(migration)
                for dep_key in migration.dependencies:
                    walk_nodes(current_app, dep_key)

        for migration_key in loader.graph.leaf_nodes():
            app_label, migration_name = migration_key
            new_app_leaf_migrations[app_label] = (app_label, migration_name)
            walk_nodes(app_label, migration_key)

        migrating_apps = []

        def find_common_ancestors(node1, node2):
            dependent_apps_1 = set()
            dependent_apps_2 = set()

            migration1 = loader.get_migration(node1[0], node1[1])
            migration2 = loader.get_migration(node2[0], node2[1])

            def walk_dependencies(migration, app_set):
                for dependency in list(loader.graph.backwards_plan((migration.app_label, migration.name)))[:-1]:
                    app_label, migration_name = dependency

                    if app_label not in migrating_apps:
                        continue
                    else:
                        app_set.add(app_label)

                    dep_migration = loader.get_migration(app_label, migration_name)
                    walk_dependencies(dep_migration, app_set)

            walk_dependencies(migration1, dependent_apps_1)
            walk_dependencies(migration2, dependent_apps_2)

            if dependent_apps_1.intersection(dependent_apps_2):
                return _find_common_ancestors([node1, node2])
            else:
                return []            

        for migration_key in leaf_nodes:
            app_label, migration_name = migration_key

            if migration_key not in loader.applied_migrations:      
                migrating_apps.append(app_label)

        app_pairs = combinations(migrating_apps, 2)

        for app_pair in app_pairs:
            common_ancestors = find_common_ancestors(new_app_leaf_migrations[app_pair[0]], new_app_leaf_migrations[app_pair[1]])

            if common_ancestors:
                most_recently_common = common_ancestors[-1][0]

                app_label, migration_name = most_recently_common
                migration = loader.get_migration(app_label, migration_name)

                # Check if we need to split out migrations to prevent cycles
                for migrations in new_app_migrations[app_label]:
                    if migration in migrations:
                        idx = migrations.index(migration)
                        split_migration = migrations[idx:]
                        new_app_migrations[app_label].insert(0, split_migration)

                        for migration in split_migration:
                            migrations.remove(migration)

                        break

        app_migrations = new_app_migrations

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

            project_migrations = defaultdict(list)

            # Create migrations for each individual app
            for app_label in app_migrations:
                for idx, migration_set in enumerate(app_migrations[app_label]):
                    project_migrations[app_label].append(self.create_app_migration(
                        app_label, self._make_name(idx), migration_set))

            # Resolve dependencies between the consolidated migrations and save
            for app_label, migrations in project_migrations.items():
                for migration_idx, migration in enumerate(migrations):
                    for dependency in copy(migration.dependencies):
                        # If there is a project level migration for the dependency app
                        if dependency[0] in project_migrations:
                            other_migration = None
                            dependency_migration = loader.get_migration(dependency[0], dependency[1])

                            for idx, migration_set in enumerate(app_migrations[dependency[0]]):
                                if dependency_migration in migration_set:
                                    other_migration = project_migrations[dependency[0]][idx]
                                    break

                            if other_migration is None or other_migration == migration:
                                continue

                            # And the dependency is a replaced migration
                            if dependency in other_migration.replaces:
                                migration.dependencies.remove(dependency)
                                migration.dependencies.append(
                                    (dependency[0], self._make_name(idx) + '_project'))

                    # Write the migration to disk
                    migration_filename = app_label + '_' + self._make_name(migration_idx) + '_project.py'
                    file_path = os.path.join(migrations_dir, migration_filename)
                    writer = MigrationWriter(migration)

                    with open(file_path, 'wb') as output_file:
                        output_file.write(writer.as_string())  # pragma: no branch
        except:
            # Delete the output dir to avoid a combination of new and old files
            if os.path.exists(migrations_dir):
                shutil.rmtree(migrations_dir)

            raise

    def create_app_migration(self, app_label, idx, migrations):
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

        return migration_class(idx + '_project', app_label)
