from __future__ import unicode_literals

from django.db import models


class Article(models.Model):
    time = models.DateTimeField()
    headline = models.CharField(max_length=64)
    content = models.CharField(max_length=32768)

    # Hack to get around tests wanting to create tables
    class Meta:
        managed = False
