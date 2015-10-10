from __future__ import unicode_literals

from collections import defaultdict
from importlib import import_module

import errno
import os
import sys

from django.apps import apps
from django.conf import settings
from django.db.migrations.loader import MigrationLoader


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
