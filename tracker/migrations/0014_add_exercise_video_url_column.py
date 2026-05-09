from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0013_alter_exercise_body_area"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AddField(
                    model_name="exercise",
                    name="video_url",
                    field=models.URLField(blank=True, default=""),
                ),
            ],
            state_operations=[],
        ),
    ]
