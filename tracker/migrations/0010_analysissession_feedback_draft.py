from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0009_plan_requires_analysis'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='physio_feedback_draft',
            field=models.TextField(blank=True),
        ),
    ]
