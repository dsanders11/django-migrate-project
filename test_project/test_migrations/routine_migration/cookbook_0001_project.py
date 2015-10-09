# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    replaces = [('cookbook', '0004_auto_20150515_0006'), ('cookbook', '0005_cookware'), ('cookbook', '0006_ingredient_tags')]

    dependencies = [
        ('blog', '0001_project'),
        ('cookbook', '0003_auto_20150514_1515'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cookware',
            name='recipes',
        ),
        migrations.DeleteModel(
            name='Cookware',
        ),
        migrations.CreateModel(
            name='Cookware',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('name', models.CharField(max_length=32)),
                ('recipes', models.ManyToManyField(to='cookbook.Recipe')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='ingredient',
            name='tags',
            field=models.ManyToManyField(to='blog.Tag'),
        ),
    ]
