from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0004_creditscore_history_factors'),
    ]

    operations = [
        migrations.CreateModel(
            name='RatingRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=30, unique=True)),
                ('label', models.CharField(max_length=120)),
                ('direction', models.CharField(choices=[('INCREASE', 'Increase rating'), ('REDUCE', 'Reduce rating')], default='REDUCE', max_length=10)),
                ('points', models.PositiveIntegerField(default=0, help_text='Points per occurrence of this action.')),
                ('cap', models.PositiveIntegerField(blank=True, help_text='Optional maximum total points this factor can contribute.', null=True)),
                ('enabled', models.BooleanField(default=True)),
                ('help_text', models.CharField(blank=True, default='', max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['action'],
            },
        ),
    ]
