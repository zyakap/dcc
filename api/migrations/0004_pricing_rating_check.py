from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_creditcheckaccess'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricingsettings',
            name='price_per_rating_check',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Charged for each rating-only lookup (used by tenant auto credit-check).', max_digits=8),
        ),
        migrations.AlterField(
            model_name='pricingsettings',
            name='price_per_credit_check',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), help_text='Charged each time a tenant unlocks (pays to view) a client credit report.', max_digits=8),
        ),
        migrations.AlterField(
            model_name='apiusagelog',
            name='action',
            field=models.CharField(choices=[('CREDIT_CHECK', 'Credit check'), ('PROFILE_LOOKUP', 'Profile lookup'), ('LOANS_LOOKUP', 'Loans lookup'), ('TRANSACTIONS_LOOKUP', 'Transactions lookup'), ('FEED_SYNC', 'Feed records synced'), ('RATING_CHECK', 'Rating-only check')], max_length=30),
        ),
    ]
