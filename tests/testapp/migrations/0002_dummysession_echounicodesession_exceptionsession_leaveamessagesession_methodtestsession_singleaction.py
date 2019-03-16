# -*- coding: utf-8 -*-
# Generated by Django 1.11.12 on 2019-03-15 13:34
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('minke', '0003_auto_20190315_1422'),
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
            name='ExceptionSession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.session',),
        ),
        migrations.CreateModel(
            name='LeaveAMessageSession',
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
            name='SingleActionDummySession',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('minke.singleactionsession',),
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