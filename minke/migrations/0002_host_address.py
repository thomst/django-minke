# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-01-21 12:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('minke', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='host',
            name='address',
            field=models.CharField(default='address', max_length=128),
            preserve_default=False,
        ),
    ]