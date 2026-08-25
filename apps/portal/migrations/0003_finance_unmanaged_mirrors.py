# Generated manually — unmanaged ACCOUNTS mirrors only.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_curriculum_unmanaged_mirrors"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeeCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=40)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "db_table": "accounts_fee_category",
                "ordering": ["name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="FeeCharge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_id", models.PositiveBigIntegerField(db_index=True)),
                ("title", models.CharField(max_length=200)),
                ("academic_year", models.CharField(blank=True, max_length=20)),
                ("term", models.CharField(blank=True, max_length=40)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("amount_paid", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("status", models.CharField(default="OPEN", max_length=20)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
                (
                    "category",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="charges",
                        to="portal.feecategory",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_fee_charge",
                "ordering": ["-created_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_id", models.PositiveBigIntegerField(db_index=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("method", models.CharField(default="CASH", max_length=20)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("received_at", models.DateTimeField()),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField()),
                (
                    "charge",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=models.deletion.DO_NOTHING,
                        related_name="payments",
                        to="portal.feecharge",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_payment",
                "ordering": ["-received_at"],
                "managed": False,
            },
        ),
    ]
