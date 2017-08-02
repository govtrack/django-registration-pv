# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2017-08-02 07:35
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import picklefield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(db_index=True, max_length=32)),
                ('uid', models.CharField(max_length=128)),
                ('auth_token', picklefield.fields.PickledObjectField(editable=False)),
                ('profile', picklefield.fields.PickledObjectField(editable=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='singlesignon', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Authentication Record',
            },
        ),
        migrations.AlterUniqueTogether(
            name='authrecord',
            unique_together=set([('provider', 'uid')]),
        ),
    ]
