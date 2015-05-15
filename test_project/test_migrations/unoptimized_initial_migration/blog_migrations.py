# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    replaces = [(b'blog', '0001_initial'), (b'blog', '0002_tag')]

    dependencies = [
        ('cookbook', 'project_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('title', models.CharField(max_length=32)),
                ('recipe', models.ForeignKey(to='cookbook.Recipe')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
                ('posts', models.ManyToManyField(to=b'blog.Post')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
