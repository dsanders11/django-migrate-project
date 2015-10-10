# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Article',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('time', models.DateTimeField()),
                ('headline', models.CharField(max_length=64)),
                ('content', models.CharField(max_length=32768)),
            ],
            options={
                'managed': False,
            },
            bases=(models.Model,),
        ),
    ]
