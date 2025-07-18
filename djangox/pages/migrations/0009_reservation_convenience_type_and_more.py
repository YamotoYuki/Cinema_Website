# Generated by Django 5.0.3 on 2025-06-26 02:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0008_movie_convenience_type_movie_payment_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservation",
            name="convenience_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("7eleven", "セブンイレブン"),
                    ("famima", "ファミリーマート"),
                    ("daily", "デイリーヤマザキ"),
                    ("ministop", "ミニストップ"),
                    ("lawson", "ローソン"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="reservation",
            name="payment_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cash", "現金"),
                    ("credit_card", "クレジットカード"),
                    ("paypal", "PayPal"),
                    ("merpay", "メルペイ"),
                    ("paypay", "PayPay"),
                    ("convenience_store", "コンビニ払い"),
                ],
                max_length=20,
                null=True,
            ),
        ),
    ]
