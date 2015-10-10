from __future__ import unicode_literals

from django.core.management.commands.migrate import Command as MigrateCommand

from django_migrate_project.executor import ProjectMigrationExecutor

# Monkey patch to avoid duplicating code
import django

migrate = django.core.management.commands.migrate

migrate.MigrationExecutor = ProjectMigrationExecutor


# Overload 'migrate' to give it ability to see project-level migrations
class Command(MigrateCommand):
    help = MigrateCommand.help

    option_list = MigrateCommand.option_list
    args = MigrateCommand.args
