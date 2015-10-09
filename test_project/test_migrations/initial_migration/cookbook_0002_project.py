# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    replaces = [('cookbook', '0002_cookware'), ('cookbook', '0003_auto_20150514_1515'), ('cookbook', '0004_auto_20150515_0006'), ('cookbook', '0005_cookware'), ('cookbook', '0006_ingredient_tags')]

    dependencies = [
        ('blog', '0001_project'),
        ('cookbook', '0001_project'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='recipe',
            name='category',
            field=models.ForeignKey(to='cookbook.Category', null=True),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='Cookware',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')),
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
