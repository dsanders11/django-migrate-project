# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    replaces = [('blog', '0001_initial'), ('blog', '0002_tag')]

    dependencies = [
        ('cookbook', '0001_project'),
    ]

    operations = [
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
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
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
                ('posts', models.ManyToManyField(to='blog.Post')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
