from __future__ import unicode_literals

from django.db import models


class Article(models.Model):
    time = models.DateTimeField()
    headline = models.CharField(max_length=64)
    content = models.CharField(max_length=32768)

    class Meta:
        managed = False
