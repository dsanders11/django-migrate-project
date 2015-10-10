from __future__ import unicode_literals

from collections import defaultdict
from importlib import import_module

import errno
import os
import sys

from django.apps import apps
from django.conf import settings
from django.db.migrations.graph import MigrationGraph
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils import six
from django.utils.encoding import python_2_unicode_compatible


PROJECT_MIGRATIONS_MODULE_NAME = 'migrations'
DEFAULT_PENDING_MIGRATIONS_DIRECTORY = 'pending_migrations'


class ProjectMigrationLoaderMixin(object):
    def get_app_migrations(self, migrations_dir, non_package=False,
                           ignore_missing_directory=True):
        migrations_by_app = defaultdict(list)
        directory_exists = os.path.isdir(migrations_dir)

        if ignore_missing_directory and not directory_exists:
            return  # Should be dealt with in the command for commands who care
        elif not directory_exists:  # pragma: no cover
            raise IOError(errno.ENOENT,
                          "No such directory: " + migrations_dir,
                          migrations_dir)

        migration_names = []

        # Code cribbed from standard MigrationLoader class
        for name in os.listdir(migrations_dir):
            is_file = os.path.isfile(os.path.join(migrations_dir, name))

            if is_file and name.endswith('.py'):
                import_name = name.rsplit('.', 1)[0]
                if import_name[0] not in '_.~':
                    migration_names.append(import_name)

        for app_config in apps.get_app_configs():
            app_label = app_config.label

            app_migration_files = [
                name for name in migration_names if name.startswith(app_label)
            ]

            for migration_file in app_migration_files:
                migration_name = migration_file.lstrip(app_label)[1:]

                try:
                    if non_package:
                        sys.path.insert(0, migrations_dir)
                        module = import_module(migration_file)
                    else:
                        module_name = (
                            "%s.%s" % (PROJECT_MIGRATIONS_MODULE_NAME,
                                       migration_file)
                        )
                        module = import_module(module_name)
                finally:
                    if non_package:
                        sys.path.pop(0)

                migrations_by_app[app_label].append(
                    module.Migration(migration_name, app_label))

        return migrations_by_app

    def load_project_disk(self):
        """ Loads the migrations for the project from disk. """

        project_migrations = {}
        migrations_dir = os.path.join(
            settings.BASE_DIR, PROJECT_MIGRATIONS_MODULE_NAME)

        app_migrations = self.get_app_migrations(
            migrations_dir, ignore_missing_directory=True)

        if app_migrations is None:
            return {}

        for app_label, migrations in app_migrations.items():
            for migration in migrations:
                self.migrated_apps.add(app_label)  # Make sure the app's listed
                self.disk_migrations[app_label, migration.name] = migration
                project_migrations[app_label, migration.name] = migration

        return project_migrations

    # XXX - This is broke in 1.7 with regards to replaces so we need to copy it
    def build_graph(self):  # pragma: no cover
        """
        Builds a migration dependency graph using both the disk and database.
        You'll need to rebuild the graph if you apply migrations. This isn't
        usually a problem as generally migration stuff runs in a one-shot
        process.
        """
        # Load disk data
        self.load_disk()
        # Load database data
        if self.connection is None:
            self.applied_migrations = set()
        else:
            recorder = MigrationRecorder(self.connection)
            self.applied_migrations = recorder.applied_migrations()
        # Do first pass to separate out replacing and non-replacing migrations
        normal = {}
        replacing = {}
        for key, migration in self.disk_migrations.items():
            if migration.replaces:
                replacing[key] = migration
            else:
                normal[key] = migration
        # Calculate reverse dependencies - i.e., for each migration,
        # what depends on it?
        # This is just for dependency re-pointing when applying replacements,
        # so we ignore run_before here.
        reverse_dependencies = {}
        for key, migration in normal.items():
            for parent in migration.dependencies:
                reverse_dependencies.setdefault(parent, set()).add(key)
        # Remember the possible replacements to generate more meaningful error
        # messages
        reverse_replacements = {}
        for key, migration in replacing.items():
            for replaced in migration.replaces:
                reverse_replacements.setdefault(replaced, set()).add(key)
        # Carry out replacements if we can - that is, if all replaced migration
        # are either unapplied or missing.
        for key, migration in replacing.items():
            # Ensure this replacement migration is not in applied_migrations
            self.applied_migrations.discard(key)
            # Do the check. We can replace if all our replace targets are
            # applied, or if all of them are unapplied.
            applied = self.applied_migrations
            replaces = migration.replaces
            applied_statuses = [(target in applied) for target in replaces]
            can_replace = all(applied_statuses) or (not any(applied_statuses))
            if not can_replace:
                continue
            # Alright, time to replace. Step through the replaced migrations
            # and remove, repointing dependencies if needs be.
            for replaced in migration.replaces:
                if replaced in normal:
                    # We don't care if the replaced migration doesn't exist;
                    # the usage pattern here is to delete things after a while.
                    del normal[replaced]
                for child_key in reverse_dependencies.get(replaced, set()):
                    if child_key in migration.replaces:
                        continue
                    # List of migrations whose dependency on `replaced` needs
                    # to be updated to a dependency on `key`.
                    to_update = []
                    # Child key may itself be replaced, in which case it might
                    # not be in `normal` anymore (depending on whether we've
                    # processed its replacement yet). If it's present, we go
                    # ahead and update it; it may be deleted later on if it is
                    # replaced, but there's no harm in updating it regardless.
                    if child_key in normal:
                        to_update.append(normal[child_key])
                    # If the child key is replaced, we update its replacement's
                    # dependencies too, if necessary. (We don't know if this
                    # replacement will actually take effect or not, but either
                    # way it's OK to update the replacing migration).
                    if child_key in reverse_replacements:
                        for replaces_ck in reverse_replacements[child_key]:
                            if replaced in replacing[replaces_ck].dependencies:
                                to_update.append(replacing[replaces_ck])
                    # Actually perform the dependency update on all migrations
                    # that require it.
                    for migration_needing_update in to_update:
                        migration_needing_update.dependencies.remove(replaced)
                        migration_needing_update.dependencies.append(key)
            normal[key] = migration
            # Mark the replacement as applied if all its replaced ones are
            if all(applied_statuses):
                self.applied_migrations.add(key)
        # Store the replacement migrations for later checks
        self.replacements = replacing
        # Finally, make a graph and load everything into it
        self.graph = MigrationGraph()
        for key, migration in normal.items():
            self.graph.add_node(key, migration)

        def _reraise_missing_dependency(migration, missing, exc):
            """
            Checks if ``missing`` could have been replaced by any squash
            migration but wasn't because the the squash migration was partially
            applied before. In that case raise a more understandable exception.
            #23556
            """
            if missing in reverse_replacements:
                candidates = reverse_replacements.get(missing, set())
                nodes = self.graph.nodees
                is_replaced = \
                    any(candidate in nodes for candidate in candidates)
                if not is_replaced:
                    tries = ', '.join('%s.%s' % c for c in candidates)
                    exc_value = NodeNotFoundError(
                        "Migration {0} depends on nonexistent node "
                        "('{1}', '{2}'). Django tried to replace migration "
                        "{1}.{2} with any of [{3}] but wasn't able to because "
                        "some of the replaced migrations are already "
                        "applied.".format(
                            migration, missing[0], missing[1], tries
                        ),
                        missing)
                    exc_value.__cause__ = exc
                    six.reraise(
                        NodeNotFoundError, exc_value, sys.exc_info()[2])
            raise exc

        # Add all internal dependencies first to ensure __first__ dependencies
        # find the correct root node.
        for key, migration in normal.items():
            for parent in migration.dependencies:
                if parent[0] != key[0] or parent[1] == '__first__':
                    # Ignore __first__ references to the same app (#22325)
                    continue
                try:
                    self.graph.add_dependency(migration, key, parent)
                except NodeNotFoundError as e:
                    # Since we added "key" to the nodes before this implies
                    # "parent" is not in there. To make the raised exception
                    # more understandable we check if parent could have been
                    # replaced but hasn't (eg partially applied squashed
                    # migration)
                    _reraise_missing_dependency(migration, parent, e)
        for key, migration in normal.items():
            for parent in migration.dependencies:
                if parent[0] == key[0]:
                    # Internal dependencies already added.
                    continue
                parent = self.check_key(parent, key[0])
                if parent is not None:
                    try:
                        self.graph.add_dependency(migration, key, parent)
                    except NodeNotFoundError as e:
                        # Since we added "key" to the nodes before this implies
                        # "parent" is not in there.
                        _reraise_missing_dependency(migration, parent, e)
            for child in migration.run_before:
                child = self.check_key(child, key[0])
                if child is not None:
                    try:
                        self.graph.add_dependency(migration, child, key)
                    except NodeNotFoundError as e:
                        # Since we added "key" to the nodes before this implies
                        # "child" is not in there.
                        _reraise_missing_dependency(migration, child, e)


class ProjectMigrationLoader(ProjectMigrationLoaderMixin, MigrationLoader):
    def load_disk(self):
        """ Loads the migrations for the project from disk. """

        # Load app migrations for dependencies
        super(ProjectMigrationLoader, self).load_disk()

        # Now load project migrations
        self.project_migrations = self.load_project_disk()

        try:
            project_migrations = settings.PROJECT_MIGRATIONS
        except AttributeError:
            project_migrations = []

        for app_label in project_migrations:
            self.migrated_apps.add(app_label)
            self.unmigrated_apps.discard(app_label)


class PendingMigrationLoader(ProjectMigrationLoaderMixin, MigrationLoader):
    def __init__(self, *args, **kwargs):
        self.pending_migrations_dir = kwargs.pop('pending_migrations_dir')

        super(PendingMigrationLoader, self).__init__(*args, **kwargs)

    def load_disk(self):
        """ Loads the pending migrations from disk. """

        self.pending_migrations = {}

        # Load app migrations for dependencies
        super(PendingMigrationLoader, self).load_disk()

        # Load project-level migrations for dependencies
        self.load_project_disk()

        # Finally load the pending migrations that we actually want
        pending_migrations = self.get_app_migrations(
            self.pending_migrations_dir, non_package=True)

        for app_label, migrations in pending_migrations.items():
            for migration in migrations:
                self.disk_migrations[app_label, migration.name] = migration
                self.pending_migrations[app_label, migration.name] = migration


@python_2_unicode_compatible
class NodeNotFoundError(LookupError):  # pragma: no cover
    """
    Raised when an attempt on a node is made that is not available in the
    graph.

    """

    def __init__(self, message, node):
        self.message = message
        self.node = node

    def __str__(self):
        return self.message

    def __repr__(self):
        return "NodeNotFoundError(%r)" % self.node
