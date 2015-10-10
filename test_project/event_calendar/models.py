from __future__ import unicode_literals

from django.db import models


class Event(models.Model):
    time = models.DateTimeField()
    description = models.CharField(max_length=128)
