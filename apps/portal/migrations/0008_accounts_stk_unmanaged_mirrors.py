# Generated manually — unmanaged ACCOUNTS STK / Daraja mirrors for parent payments.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0007_student_conduct_unmanaged_mirror"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchoolAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(max_length=32)),
                ("custom_category", models.CharField(blank=True, max_length=120)),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("payment_modes", models.JSONField(default=list)),
                ("academic_level_ids", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField()),
            ],
            options={
                "db_table": "accounts_school_account",
                "ordering": ["category", "name"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="DarajaSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("active_environment", models.CharField(default="SANDBOX", max_length=20)),
                ("is_enabled", models.BooleanField(default=False)),
                ("sandbox_consumer_key", models.CharField(blank=True, max_length=255)),
                ("sandbox_consumer_secret", models.CharField(blank=True, max_length=255)),
                ("sandbox_shortcode", models.CharField(blank=True, max_length=20)),
                ("sandbox_passkey", models.CharField(blank=True, max_length=255)),
                ("sandbox_callback_url", models.URLField(blank=True)),
                ("production_consumer_key", models.CharField(blank=True, max_length=255)),
                ("production_consumer_secret", models.CharField(blank=True, max_length=255)),
                ("production_shortcode", models.CharField(blank=True, max_length=20)),
                ("production_passkey", models.CharField(blank=True, max_length=255)),
                ("production_callback_url", models.URLField(blank=True)),
                ("updated_at", models.DateTimeField()),
            ],
            options={
                "db_table": "accounts_daraja_settings",
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="MpesaCallbackLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("merchant_request_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("checkout_request_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("result_code", models.IntegerField(blank=True, null=True)),
                ("result_desc", models.CharField(blank=True, max_length=255)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("mpesa_receipt", models.CharField(blank=True, db_index=True, max_length=64)),
                ("phone_number", models.CharField(blank=True, max_length=20)),
                ("status", models.CharField(default="RECEIVED", max_length=20)),
                ("payment_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField()),
            ],
            options={
                "db_table": "accounts_mpesa_callback_log",
                "ordering": ["-created_at"],
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="StkPushRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_id", models.PositiveBigIntegerField(db_index=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("phone_number", models.CharField(max_length=20)),
                ("account_reference", models.CharField(blank=True, max_length=120)),
                ("merchant_request_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("checkout_request_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("mpesa_receipt", models.CharField(blank=True, db_index=True, max_length=64)),
                ("result_code", models.IntegerField(blank=True, null=True)),
                ("result_desc", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(db_index=True, default="PENDING", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("created_by_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("payment_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="stk_push_requests",
                        to="portal.schoolaccount",
                    ),
                ),
            ],
            options={
                "db_table": "accounts_stk_push_request",
                "ordering": ["-created_at"],
                "managed": False,
            },
        ),
    ]
