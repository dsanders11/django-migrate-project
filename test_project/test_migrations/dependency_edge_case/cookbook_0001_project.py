# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    replaces = [('cookbook', '0006_ingredient_tags')]

    dependencies = [
        ('blog', '0002_tag'),
        ('cookbook', '0005_cookware'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingredient',
            name='tags',
            field=models.ManyToManyField(to='blog.Tag'),
        ),
    ]

