# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2018-02-19 12:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Host',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host', models.SlugField(max_length=128, unique=True)),
                ('user', models.SlugField(max_length=128)),
                ('hostname', models.CharField(max_length=128)),
                ('port', models.SmallIntegerField(blank=True, null=True)),
                ('hoststring', models.CharField(max_length=255, unique=True)),
                ('disabled', models.BooleanField(default=False)),
                ('locked', models.BooleanField(default=False)),
            ],
        ),
    ]
