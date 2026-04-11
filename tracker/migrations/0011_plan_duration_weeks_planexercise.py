from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0010_analysissession_feedback_draft'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='duration_weeks',
            field=models.PositiveIntegerField(default=6),
        ),
        migrations.CreateModel(
            name='PlanExercise',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sets', models.PositiveIntegerField(default=3)),
                ('reps', models.PositiveIntegerField(default=10)),
                ('order', models.PositiveIntegerField(default=0)),
                ('exercise', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracker.exercise')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plan_exercises', to='tracker.plan')),
            ],
            options={
                'ordering': ['order', 'id'],
                'unique_together': {('plan', 'exercise')},
            },
        ),
    ]
