from __future__ import unicode_literals

from django.db.migrations.executor import MigrationExecutor

from django_migrate_project.loader import ProjectMigrationLoader


class ProjectMigrationExecutor(MigrationExecutor):
    def __init__(self, connection, progress_callback=None):
        super(ProjectMigrationExecutor, self).__init__(
            connection, progress_callback)

        # Change out the migration loader
        self.loader = ProjectMigrationLoader(self.connection)
