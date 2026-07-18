from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_pricing_rating_check'),
        ('users', '0002_userprofile_credit_check_window_hours'),
    ]

    operations = [
        migrations.AddField(
            model_name='apiusagelog',
            name='unit_price',
            field=models.DecimalField(blank=True, decimal_places=4, help_text='Price per unit at the time of the event — later pricing changes never alter past bills. Null on legacy rows (billed at current pricing).', max_digits=10, null=True),
        ),
        migrations.CreateModel(
            name='BillingSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('auto_send_enabled', models.BooleanField(default=False, help_text="When on, last month's invoice is generated and emailed to every active tenant automatically on the send day.")),
                ('send_day', models.PositiveIntegerField(default=3, help_text='Day of the month (1-28) the automatic invoice run fires.')),
                ('cc_email', models.CharField(blank=True, default='', help_text='Optional address CC-ed on every invoice email.', max_length=255)),
            ],
            options={
                'verbose_name': 'Billing settings',
                'verbose_name_plural': 'Billing settings',
            },
        ),
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.PositiveIntegerField()),
                ('month', models.PositiveIntegerField()),
                ('number', models.CharField(max_length=30, unique=True)),
                ('currency', models.CharField(default='PGK', max_length=10)),
                ('base_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('lines', models.JSONField(default=list, help_text='[{action, label, units, unit_price, cost}, ...]')),
                ('total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('status', models.CharField(choices=[('DRAFT', 'DRAFT'), ('SENT', 'SENT'), ('PAID', 'PAID')], default='DRAFT', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='users.userprofile')),
            ],
            options={
                'ordering': ['-year', '-month', 'tenant_id'],
                'unique_together': {('tenant', 'year', 'month')},
            },
        ),
    ]
