from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0005_plan_created_by'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AnalysisSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('exercise_name', models.CharField(default='Squat', max_length=100)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('total_frames', models.IntegerField(default=0)),
                ('flagged_frames', models.IntegerField(default=0)),
                ('summary_json', models.TextField(blank=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analysis_sessions', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='analysis_sessions_created', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
