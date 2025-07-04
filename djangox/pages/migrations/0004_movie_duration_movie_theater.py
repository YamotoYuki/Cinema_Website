# Generated by Django 5.0.3 on 2025-06-20 03:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0003_movie_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="movie",
            name="duration",
            field=models.PositiveIntegerField(
                blank=True, help_text="上映時間（分）", null=True
            ),
        ),
        migrations.AddField(
            model_name="movie",
            name="theater",
            field=models.CharField(
                blank=True, help_text="シアター名", max_length=100, null=True
            ),
        ),
    ]
