# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    replaces = [(b'cookbook', '0001_initial'), (b'cookbook', '0002_cookware'), (b'cookbook', '0003_auto_20150514_1515'), (b'cookbook', '0004_auto_20150515_0006'), (b'cookbook', '0005_cookware')]

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Ingredient',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RecipeIngredient',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('quantity', models.IntegerField()),
                ('ingredient', models.ForeignKey(to='cookbook.Ingredient')),
                ('recipe', models.ForeignKey(to='cookbook.Recipe')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='recipe',
            name='ingredients',
            field=models.ManyToManyField(to=b'cookbook.Ingredient', through='cookbook.RecipeIngredient'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='ingredient',
            name='recipes',
            field=models.ManyToManyField(to=b'cookbook.Recipe', through='cookbook.RecipeIngredient'),
            preserve_default=True,
        ),
        migrations.CreateModel(
            name='Cookware',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
                ('recipes', models.ManyToManyField(to=b'cookbook.Recipe')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='recipe',
            name='category',
            field=models.ForeignKey(null=True, to='cookbook.Category'),
            preserve_default=True,
        ),
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
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
                ('recipes', models.ManyToManyField(to=b'cookbook.Recipe')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
