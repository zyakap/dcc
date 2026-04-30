from django.db import models

from client.models import ClientProfile
from users.models import UserProfile
from loan.models import Loan

# Create your models here.
class Transaction(models.Model):
    
    lender = models.ForeignKey(UserProfile, on_delete=models.PROTECT, null=True, blank=True)
    owner = models.ForeignKey(ClientProfile, on_delete=models.PROTECT, null=True, blank=True)

    uid = models.CharField(max_length=50, blank=True, null=True)
    luid = models.CharField(max_length=50, blank=True, null=True)
    
    ref = models.CharField(max_length=50, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    type = models.CharField(max_length=255, choices=[('PAYMENT','PAYMENT'), ('DEFAULT', 'DEFAULT'), ('OTHER', 'OTHER')], blank=True, null=True)
    s_count = models.IntegerField(blank=True, null=True, default=0)
    loanref = models.ForeignKey(Loan, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateTimeField()
    
    statement = models.CharField(max_length=255, null=True, blank=True)
    debit = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    credit = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    arrears = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    balance = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)

    #optional for those who seperate loan , processing fee and interest (beyond finance logic) or for those who want to track interest on default
    default_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    interest_on_default = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    default_interest_collected = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    loan_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    application_fee = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    interest = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)