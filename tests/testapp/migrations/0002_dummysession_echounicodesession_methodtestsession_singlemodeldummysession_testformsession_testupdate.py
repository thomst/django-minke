# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2018-12-16 22:56
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('minke', '0004_auto_20181212_1111'),
        ('testapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='DummySession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.session',),
        ),
        migrations.CreateModel(
            name='EchoUnicodeSession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.session',),
        ),
        migrations.CreateModel(
            name='MethodTestSession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.updateentriessession',),
        ),
        migrations.CreateModel(
            name='SingleModelDummySession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.session',),
        ),
        migrations.CreateModel(
            name='TestFormSession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.session',),
        ),
        migrations.CreateModel(
            name='TestUpdateEntriesSession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.updateentriessession',),
        ),
    ]
