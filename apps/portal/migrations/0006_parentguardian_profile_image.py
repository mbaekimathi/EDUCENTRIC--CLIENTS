# Unmanaged state sync — column is owned by ADMINISTRATION admissions.0012.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0005_school_activity_unmanaged_mirrors"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="parentguardian",
                    name="profile_image",
                    field=models.CharField(blank=True, max_length=100),
                ),
            ],
            database_operations=[],
        ),
    ]
