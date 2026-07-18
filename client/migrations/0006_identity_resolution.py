import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0005_ratingrule'),
    ]

    operations = [
        migrations.CreateModel(
            name='IdentityExclusion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.CharField(blank=True, default='', max_length=100)),
                ('profile_a', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exclusions_a', to='client.clientprofile')),
                ('profile_b', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='exclusions_b', to='client.clientprofile')),
            ],
            options={
                'unique_together': {('profile_a', 'profile_b')},
            },
        ),
        migrations.CreateModel(
            name='IdentityCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('AUTO', 'Auto-linked — confirm'), ('REVIEW', 'Ambiguous — needs review')], default='REVIEW', max_length=10)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('LINKED', 'Confirmed same person'), ('MERGED', 'Merged into one profile'), ('DISMISSED', 'Different people')], default='PENDING', max_length=10)),
                ('signature', models.CharField(help_text='Stable hash of the sorted member ids (dedupes rescans).', max_length=64, unique=True)),
                ('member_ids', models.JSONField(default=list)),
                ('display_name', models.CharField(blank=True, default='', max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_by', models.CharField(blank=True, default='', max_length=100)),
                ('note', models.CharField(blank=True, default='', max_length=255)),
                ('primary', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='identity_primary_cases', to='client.clientprofile')),
            ],
            options={
                'ordering': ['status', '-created_at'],
            },
        ),
    ]
