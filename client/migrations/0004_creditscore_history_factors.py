from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('client', '0003_clientcreditscore'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientcreditscore',
            name='tenants_reporting',
            field=models.IntegerField(default=0, help_text='Distinct tenants holding a profile for this person.'),
        ),
        migrations.AddField(
            model_name='clientcreditscore',
            name='identity_changes',
            field=models.IntegerField(default=0, help_text='Times identity fields (name/DOB/IDs) were changed after first capture.'),
        ),
        migrations.AddField(
            model_name='clientcreditscore',
            name='status_events',
            field=models.IntegerField(default=0, help_text='Historical DEFAULT/RECOVERY/BAD/BLACKLIST episodes, even if since cleared.'),
        ),
        migrations.AddField(
            model_name='clientcreditscore',
            name='months_active',
            field=models.IntegerField(default=0, help_text='Distinct months with repayment activity on record.'),
        ),
    ]
