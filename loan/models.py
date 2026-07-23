from django.conf import settings
from django.db import models

from client.models import ClientProfile
from users.models import UserProfile
#from admin1.models import Location

import os
from django.conf import settings
from django.db import models

#pre-delete SIGNALS
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from users.models import UserProfile, User
#from admin1.models import Location

import json


def loan_file_path(instance, filename):
    # Determine the upload path for car invoices
    return os.path.join('loanfiles',filename)

# Create your models here.
class Loan(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    ref = models.CharField(max_length=50, blank=True, null=True)
    UID = models.CharField(max_length=30, blank=True, null=True)
    LUID = models.CharField(max_length=30, blank=True, null=True)
    existing_code = models.CharField(max_length=30, blank=True, null=True)
    lender = models.ForeignKey(UserProfile, on_delete=models.PROTECT,null=True, blank=True)
    owner = models.ForeignKey(ClientProfile, on_delete=models.PROTECT,null=True, blank=True)
    officer = models.IntegerField(null=True, blank=True)
    #agent = models.ForeignKey(AgentProfile, on_delete=models.PROTECT,null=True, blank=True)
    location = models.IntegerField(null=True, blank=True)
    loan_type = models.CharField("Loan Type:", max_length=30, blank=True, null=True,choices=[('PERSONAL', 'PERSONAL'),('SME','SME')], default="PERSONAL")
    classification = models.CharField("Loan Classification:", max_length=30, blank=True, null=True,choices=[('ADDITIONAL', 'ADDITIONAL'),('REFINANCED', 'REFINANCED'),('NEW','NEW')], default="NEW")
    
    application_date = models.DateField(auto_now=True, null=True)
    amount = models.DecimalField(verbose_name='LOAN AMOUNT:', max_digits=8, decimal_places=2, null=True)
    processing_fee = models.DecimalField(verbose_name='PROCESSING FEE:', max_digits=7, decimal_places=2, blank=True, null=True, default=0.00)
    interest = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    total_loan_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    repayment_frequency = models.CharField(choices=[('FORTNIGHTLY', 'FORTNIGHTLY'),('MONTHLY','MONTHLY')], max_length=30, blank=True, null=True, default='FORTNIGHTLY')
    number_of_fortnights = models.IntegerField(verbose_name='Number of Fortnights:', null=True)
    repayment_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
   
    category = models.CharField(max_length=30, blank=True, null=True,choices=[('PENDING','PENDING'),('FUNDED','FUNDED')])
    funded_category = models.CharField(max_length=30, blank=True, null=True,choices=[('ACTIVE','ACTIVE'), ('RECOVERY', 'RECOVERY'), ('BAD','BAD'), ('WOFF','WOFF'), ('COMPLETED','COMPLETED'), ('ARCHIVED','ARCHIVED')])
    status = models.CharField(max_length=30, blank=True, null=True,choices=[('AWAITING T&C', 'AWAITING T&C'),('UNDER REVIEW','UNDER REVIEW'),('ON HOLD','ON HOLD'),('APPROVED','APPROVED'),('REJECTED','REJECTED'),('RUNNING','RUNNING'),('DEFAULTED','DEFAULTED'),('COMPLETED','COMPLETED')])
    
    tc_agreement = models.CharField(max_length=3, blank=True, null=True, choices=[('YES', 'YES'),('NO', 'NO')])
    tc_agreement_timestamp = models.DateTimeField(blank=True, null=True)
    funding_date = models.DateField(verbose_name='Funding Date:', blank=True, null=True)
    repayment_start_date = models.DateField(verbose_name='Repayment Start Date:', null=True)
    expected_end_date = models.DateField(verbose_name='Expected end Date:', null=True)
    repayment_dates = models.TextField(null=True, blank=True)  # Store dates as JSON string
    next_payment_date = models.DateField(blank=True, null=True)
    
    principal_loan_paid = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    interest_paid = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    default_interest_paid = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #total_default_interest_repaid = 
    total_paid = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)

    fortnights_paid = models.IntegerField(verbose_name='Number of Fortnights Paid:', null=True, blank=True, default=0)
    number_of_repayments = models.IntegerField(blank=True, null=True, default=0)
    last_repayment_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    last_repayment_date = models.DateField(blank=True, null=True)
    
    number_of_advance_payments = models.IntegerField(blank=True, null=True, default=0)
    last_advance_payment_date = models.DateField(blank=True, null=True)
    last_advance_payment_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    total_advance_payment = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0.00)
    advance_payment_surplus = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0.00)
    
    number_of_defaults = models.IntegerField(blank=True, null=True, default=0)
    last_default_date = models.DateField(blank=True, null=True)
    last_default_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    days_in_default = models.IntegerField(blank=True, null=True, default=0)
    total_arrears = models.DecimalField(max_digits=8, decimal_places=2, blank=True, default=0.00)

    #trupngfinance
    #optional (beyond finance logic)
    
    principal_loan_receivable = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)  #amount_remaining = 
    ordinary_interest_receivable = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #oridinary_interest_receivable = 
    default_interest_receivable = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #default_interest_receivable = 
    total_outstanding = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #total_receivable_amount 

    turnover_days = models.IntegerField(blank=True, null=True, default=0)
    aging_category = models.CharField(max_length=100, blank=True, null=True, choices=[('30LESS', '30LESS'),('30TO90', '30TO90'),('90TO180', '90TO180'),('180PLUS','180PLUS')])
    aging_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, default=0.00)
    considered_unrecoverable = models.DecimalField(max_digits=8, decimal_places=2, blank=True, default=0.00)
    recovery_date = models.DateField(blank=True, null=True)

    opt1 = models.CharField(max_length=20, blank=True, null=True)
    opt2 = models.CharField(max_length=20, blank=True, null=True)
    opt3 = models.CharField(max_length=20, blank=True, null=True)
    opt4 = models.CharField(max_length=20, blank=True, null=True)
    opt5 = models.CharField(max_length=20, blank=True, null=True)

    dcc = models.CharField(max_length=20, blank=True, null=True,default='')
    notes = models.TextField(blank=True, null=True)

    def get_repayment_dates(self):
        if self.repayment_dates:
            return json.loads(self.repayment_dates)
        return []

    def set_repayment_dates(self, dates):
        self.repayment_dates = json.dumps(dates)

    def formatted_amount(self):
        return "{:,.2f}".format(self.amount)
    
    def formatted_repayment_amount(self):
        return "{:,.2f}".format(self.repayment_amount)
    
    def __str__(self):
        return f'{self.ref}'
    
    class Meta:
        ordering = ['-funding_date']  # Assuming 'date' is a field in your Loan model
        verbose_name = 'Loan'
        verbose_name_plural = 'Loans'

class LoanFile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    loan = models.OneToOneField(Loan, related_name='files', on_delete=models.CASCADE)
    
    #required uploads
    application_form = models.FileField('Application Form:', upload_to=loan_file_path, null=True, blank=True)
    application_form_url = models.CharField(max_length=555, null=True, blank=True)
    
    terms_conditions = models.FileField('Terms & Conditions:', upload_to=loan_file_path, null=True, blank=True)
    terms_conditions_url = models.CharField(max_length=555, null=True, blank=True)

    stat_dec = models.FileField('Statutory Declaration:', upload_to=loan_file_path, null=True, blank=True)
    stat_dec_url = models.CharField(max_length=555, null=True, blank=True)
    
    irr_sd_form = models.FileField('Irrevocable Salary Deduction Authority:', upload_to=loan_file_path, null=True, blank=True)
    irr_sd_form_url = models.CharField(max_length=555, null=True, blank=True)

    #work required uploads
    work_confirmation_letter = models.FileField('Work Confirmation Letter:', upload_to=loan_file_path, null=True, blank=True)
    work_confirmation_letter_url = models.CharField(max_length=555, null=True, blank=True)

    payslip1 = models.FileField('Payslip 1:', null=True, upload_to=loan_file_path, blank=True)
    payslip1_url = models.CharField(max_length=555, null=True, blank=True)

    payslip2 = models.FileField('Payslip 2:', null=True, upload_to=loan_file_path, blank=True)
    payslip2_url = models.CharField(max_length=555, null=True, blank=True)

    #statement Uploads

    loan_statement1 = models.FileField('Loan Statement 1:', upload_to=loan_file_path, null=True, blank=True)
    loan_statement1_url = models.CharField(max_length=555, null=True, blank=True)
    
    loan_statement2 = models.FileField('Loan Statement 2:', upload_to=loan_file_path, null=True, blank=True)
    loan_statement2_url = models.CharField(max_length=555, null=True, blank=True)

    loan_statement3 = models.FileField('Loan Statement 3:', upload_to=loan_file_path, null=True, blank=True)
    loan_statement3_url = models.CharField(max_length=555, null=True, blank=True)
    
    bank_statement = models.FileField('Bank Statement:', upload_to=loan_file_path, null=True, blank=True)
    bank_statement_url = models.CharField(max_length=555, null=True, blank=True)

    super_statement = models.FileField('Super Statement:', upload_to=loan_file_path, null=True, blank=True)
    super_statement_url = models.CharField(max_length=555, null=True, blank=True)

    bank_standing_order = models.FileField('Bank Standing Order:', upload_to=loan_file_path, null=True, blank=True)
    bank_standing_order_url = models.CharField(max_length=555, null=True, blank=True)

    #funding 
    funding_receipt = models.FileField('Funding Receipt:', upload_to=loan_file_path, null=True, blank=True)
    funding_receipt_url = models.CharField(max_length=555, null=True, blank=True)

class Statement(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    ref = models.CharField(max_length=50, blank=True, null=True)
    uid = models.CharField(max_length=50, blank=True, null=True)
    luid = models.CharField(max_length=50, blank=True, null=True)
    owner = models.ForeignKey(UserProfile, on_delete=models.PROTECT, null=True, blank=True)
    loanref = models.ForeignKey(Loan, on_delete=models.CASCADE, null=True, blank=True)
    
    date = models.DateTimeField()
    statement_type = models.CharField(max_length=255, choices=[('PAYMENT','PAYMENT'), ('DEFAULT', 'DEFAULT'), ('OTHER', 'OTHER')], blank=True, null=True)
    s_count = models.IntegerField(blank=True, null=True, default=0)
    
    statement = models.CharField(max_length=255, null=True, blank=True)
    debit = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    credit = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    arrears = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    balance = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)

    default_amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)
    default_interest = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #added to loan total

    #optional for those who seperate loan , interest (beyond finance logic) or for those who want to track interest on default
    principal_collected = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #principal_loan_receipted
    interest_collected = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)  #interest_earned_receipted
    default_interest_collected = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0) #default_interest_receipted

    dcc = models.CharField(max_length=30, null=True, blank=True)

class PaymentUploads(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ref = models.CharField(max_length=30, null=True, blank=True)
    owner =  models.ForeignKey(UserProfile, on_delete=models.PROTECT, null=True, blank=True)
    loan =  models.ForeignKey(Loan, on_delete=models.CASCADE, null=True, blank=True)
    payment_proof = models.FileField(null=True, blank=True)
    
    payment_type = models.CharField(max_length=55, null=True, blank=True, choices=[('NORMAL REPAYMENT','NORMAL REPAYMENT'),('ADVANCE PAYMENT', 'ADVANCE PAYMENT')])
    file_name = models.CharField(max_length=255, null=True)
    payment_proof_url = models.CharField(max_length=255, null=True)
    status = models.CharField(max_length=255, null=True, blank=True)

class Payment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(UserProfile, on_delete=models.PROTECT, null=True, blank=True)
    ref = models.CharField(max_length=50, blank=True, null=True)
    loanref =  models.ForeignKey(Loan, on_delete=models.CASCADE, null=True, blank=True)
    p_count = models.IntegerField(blank=True, null=True, default=0)
    date = models.DateField()
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_type = models.CharField(max_length=55, null=True, blank=True, choices=[('NORMAL REPAYMENT','NORMAL REPAYMENT'),('ADVANCE PAYMENT', 'ADVANCE PAYMENT'),('PARTIAL PAYMENT','PARTIAL PAYMENT')])
    mode = models.CharField(max_length=55, null=True, blank=True, choices=[('PAYROLL DEDUCTION','PAYROLL DEDUCTION'),('BANK DEPOSIT', 'BANK DEPOSIT'),('CASH','CASH')])
    statement = models.CharField(max_length=555, null=True)
    upload_id =  models.ForeignKey(PaymentUploads, on_delete=models.PROTECT, null=True, blank=True)
    officer = models.IntegerField()


# Define a function to delete associated files when a loan is deleted
@receiver(pre_delete, sender=Loan)
def delete_loan_files(sender, instance, **kwargs):
    # Get associated files for the loan
    print('SIGNAL READ')
    loan_files = LoanFile.objects.filter(loan=instance)
    print(loan_files)
    # Delete each file from the storage
    for loan_file in loan_files:
        print('ENTERED FOR LOOP')
        if loan_file.application_form:
            print('application_form exists')
            file_path = loan_file.application_form.path
            print('file_path:', file_path)
            if os.path.exists(file_path):
                print('file exists at path:', file_path)
                try:
                    os.remove(file_path)
                    print('file removed successfully')
                except Exception as e:
                    print('Error:', e)
            else:
                print('file does not exist at path:', file_path)
        else:
            print('application_form does not exist')
        # Repeat the above process for other FileField attributes as needed
        # For example:
        if loan_file.terms_conditions:
            file_path = loan_file.terms_conditions.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.stat_dec:
            file_path = loan_file.stat_dec.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.irr_sd_form:
            file_path = loan_file.irr_sd_form.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.work_confirmation_letter:
            file_path = loan_file.work_confirmation_letter.path
            if os.path.exists(file_path):
                os.remove(file_path)
        
        if loan_file.payslip1:
            file_path = loan_file.payslip1.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.payslip2:
            file_path = loan_file.payslip2.path
            if os.path.exists(file_path):
                os.remove(file_path)
#
        if loan_file.loan_statement1:
            file_path = loan_file.loan_statement1.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.loan_statement2:
            file_path = loan_file.loan_statement2.path
            if os.path.exists(file_path):
                os.remove(file_path)
              
        if loan_file.loan_statement3:
            file_path = loan_file.loan_statement3.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.bank_statement:
            file_path = loan_file.bank_statement.path
            if os.path.exists(file_path):
                os.remove(file_path)

        if loan_file.super_statement:
            file_path = loan_file.super_statement.path
            if os.path.exists(file_path):
                os.remove(file_path)
            
        if loan_file.bank_standing_order:
            file_path = loan_file.bank_standing_order.path
            if os.path.exists(file_path):
                os.remove(file_path)
        # Continue this pattern for other FileField attributes



# Repayments Models
# FOR STATEMENT GENERATION

#repayment_dates = {dictionary}


class RecoveryRecord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    lender = models.ForeignKey(UserProfile, on_delete=models.PROTECT,null=True, blank=True)
    owner = models.ForeignKey(ClientProfile, on_delete=models.PROTECT,null=True, blank=True)
    
    uid = models.CharField("UID:", max_length=30, blank=True, null=True)
    luid = models.CharField("LUID:", max_length=30, blank=True, null=True)
    category = models.CharField(max_length=10, blank=True, null=True, choices=[('CLIENT', 'CLIENT'),('BUSINESS', 'BUSINESS')], default='CLIENT')
    date = models.DateField(verbose_name='Expected end Date:', null=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True, default=0)

    

# ============================================================================
# Guarantor — links a guarantor/co-borrower ClientProfile to a Loan
# ============================================================================

class Guarantor(models.Model):
    GUARANTEE_TYPES = [
        ('PERSONAL', 'Personal Guarantee'),
        ('JOINT',    'Joint Borrower'),
        ('PARTIAL',  'Partial Guarantee'),
    ]

    loan            = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='guarantors')
    guarantor       = models.ForeignKey('client.ClientProfile', on_delete=models.CASCADE, related_name='guarantor_loans')
    guarantee_type  = models.CharField(max_length=10, choices=GUARANTEE_TYPES, default='PERSONAL')
    guarantee_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes           = models.CharField(max_length=255, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('loan', 'guarantor')]

    def __str__(self):
        return f'{self.guarantor} → {self.loan.ref} ({self.guarantee_type})'
