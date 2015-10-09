from __future__ import unicode_literals

from django.db import models

from cookbook.models import Recipe


class Post(models.Model):
    title = models.CharField(max_length=32)
    recipe = models.ForeignKey(Recipe)
    user = models.ForeignKey('auth.User')


class Tag(models.Model):
    name = models.CharField(max_length=32)
    posts = models.ManyToManyField(Post)
