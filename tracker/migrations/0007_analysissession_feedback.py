from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0006_analysissession'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysissession',
            name='physio_feedback',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='feedback_shared',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='analysissession',
            name='feedback_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
