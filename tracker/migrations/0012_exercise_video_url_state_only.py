from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0011_plan_duration_weeks_planexercise'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='exercise',
                    name='video_url',
                    field=models.URLField(blank=True, default=''),
                ),
            ],
        ),
    ]
