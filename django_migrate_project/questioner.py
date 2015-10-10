from __future__ import unicode_literals

from django.conf import settings
from django.db.migrations.questioner import InteractiveMigrationQuestioner


class ProjectInteractiveMigrationQuestioner(InteractiveMigrationQuestioner):
    def ask_initial(self, app_label):
        try:
            project_migrations = settings.PROJECT_MIGRATIONS
        except AttributeError:  # pragma: no cover
            project_migrations = []

        if app_label in project_migrations:
            return True
        else:
            questioner = super(ProjectInteractiveMigrationQuestioner, self)

            return questioner.ask_initial(app_label)
