# Generated by Django 5.0.3 on 2025-06-30 02:45

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0011_userprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShowSchedule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("screen", models.IntegerField()),
                ("format", models.CharField(blank=True, max_length=50)),
                (
                    "movie",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedules",
                        to="pages.movie",
                    ),
                ),
            ],
        ),
    ]
