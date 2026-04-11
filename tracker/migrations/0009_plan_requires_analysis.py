from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0008_analysissession_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='requires_analysis',
            field=models.BooleanField(default=False),
        ),
    ]
