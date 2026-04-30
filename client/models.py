from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.forms import DecimalField, FileField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.db import models
from users.models import UserProfile

class ClientProfile(models.Model):
  
    PROVINCE = [('AROB','AROB'),('CENTRAL','CENTRAL'),('ENGA','ENGA'),('EAST SEPIK','EAST SEPIK'),('EHP','EHP'),('ENB','ENBP'),
    ('HELA','HELA'), ('JIWAKA','JIWAKA'),('MADANG','MADANG'),('MANUS','MANUS'),('MOROBE', 'MOROBE'),('NCD','NCD'),('NEW IRELAND','NEW IRELAND'),('ORO','ORO'),
    ('SHP','SHP'),('SIMBU','SIMBU'), ('WESTERN','WESTERN'), ('WEST SEPIK','WEST SEPIK'), ('WHP','WHP'), ('WNB','WNBP'),
    ]

    DCC_STATUS_CHOICES = [
        ('DEFAULT','DEFAULT'), 
        ('RECOVERY','RECOVERY'),
        ('BAD','BAD'),
        ('BACKLIST','BLACKLIST')
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #unique identifiers
    initial_dcc = models.CharField(max_length=100,null=True, blank=True)
    CUID = models.CharField(max_length=100,null=True, blank=True)
    LUID = models.CharField(max_length=100,null=True, blank=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='client_owner', null=True, blank=True)

    credit_rating = models.DecimalField(max_digits=5, decimal_places=2, null=True, default=100.00)
    number_of_loans = models.IntegerField(null=True, blank = True, default=0)
    number_of_flagged_loans = models.IntegerField(null=True, blank = True, default=0)
    repayment_limit = models.DecimalField(verbose_name="Borrower's Limit:", max_digits=8, decimal_places=2, null=True, blank=True, default=0)

    client_type = models.CharField(max_length=20, choices=[('INDIVIDUAL','INDIVIDUAL'),('BUSINESS','BUSINESS')], default='NOT SPECIFIED', null=True, blank=True)
    #basic
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50)
    nick_name = models.CharField(max_length=50,null=True, blank=True)
    other_names = models.CharField(max_length=255,null=True, blank=True)
    gender = models.CharField(max_length=6, choices=[('MALE','MALE'),('FEMALE','FEMALE')], default='', null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=10, choices=[('SINGLE','SINGLE'),('MARRIED','MARRIED'),('DE-FACTO','DE-FACTO'),('DIVORCED','DIVORCED'),('WIDOWED','WIDOWED')], default='', null=True, blank=True)
    
    #contact
    email = models.EmailField(null=True, blank=True)
    mobile1 = models.IntegerField(null=True, blank = True)
    
    #personal_ID
    nid_number = models.CharField(max_length=20, null=True, blank=True)
    passport_number = models.CharField(max_length=20, null=True, blank=True)
    drivers_license_number = models.CharField(max_length=20, null=True, blank=True)
    super_member_code = models.CharField(max_length=20, null=True, blank=True)

    #personal_info
    place_of_origin = models.TextField(max_length=255, null=True, blank=True)
    province_of_origin = models.CharField('Province of Origin', max_length=20, choices=PROVINCE, null=True, blank=True, default="Not Specified")
    permanent_address = models.TextField(max_length=255, null=True, blank=True)
    
    #checks
    has_loan = models.BooleanField(default=False)
    dcc_flagged = models.BooleanField(default=False)
    dcc_status = models.CharField('DCC Status', max_length=20, choices=DCC_STATUS_CHOICES, null=True, blank=True, default="CLEAR")
    
    #has_arrears = models.BooleanField(default=False)
    public_listing = models.BooleanField(default=False)
    public_search = models.BooleanField(default=False)
    
    
    #comments
    dcc_comment = models.CharField(max_length=255,null=True, blank = True, default='')
    cdb_comment = models.CharField(max_length=255,null=True, blank = True, default='')
    notes = models.TextField(max_length=255, null=True, blank=True)

    vetted = models.BooleanField(default=False)
    vetting_status = models.CharField(max_length=20, choices=[('REVIEW','REVIEW'),('HOLD','HOLD'),('QUESTION','QUESTION')], default='REVIEW', null=True, blank=True)
    
    public_category = models.CharField(max_length=20, choices=[('GOOD CUSTOMER','GOOD CUSTOMER'),('IN DEFAULT','IN DEFAULT'),('IN RECOVERY','IN RECOVERY'),('HAS A BAD LOAN','HAS A BAD LOAN'),('BLACKLISTED','BLACKLISTED')], default='GOOD CUSTOMER', null=True, blank=True)
    
    
    def __str__(self):
        return f'{self.first_name} {self.last_name}'

class BusinessProfile(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    buid = models.CharField(max_length=20,null=True, blank=True)
    ref = models.CharField(max_length=20, null=True, blank=True, default='')
    public_listing = models.BooleanField(default=False)
    public_search = models.BooleanField(default=False)
    credit_rating = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=100)
    
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='record_owner', null=True, blank=True)

    business_owner = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='business_owner', null=True, blank=True)
    category = models.CharField(max_length=20, choices=[('SOLE TRADER','SOLE TRADER'),('SME','SME'),('MSME','MSME'),('COMPANY','COMPANY')], default='SME', null=True, blank=True)
    trading_name =  models.CharField(max_length=255, null=True, blank=True, default='')
    registered_name = models.CharField(max_length=255, null=True, blank=True, default='') 
    business_address = models.CharField(max_length=255, null=True, blank=True, default='')
    email = models.EmailField(null=True, blank = True)
    phone = models.CharField(max_length=10, null=True, blank=True, default='')
    website = models.CharField(max_length=100, null=True, blank=True, default='')
    ipa_registration_number = models.CharField(max_length=20, null=True, blank=True)
    tin_number = models.CharField(max_length=20, null=True, blank=True)
    #default data
    amount = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)
    date_of_committment = models.DateField(null=True, blank=True)

    vetted = models.BooleanField(default=False)
    vetting_status = models.CharField(max_length=20, choices=[('REVIEW','REVIEW'),('HOLD','HOLD'),('QUESTION','QUESTION'),('VETTED','VETTED')], default='REVIEW', null=True, blank=True)

    public_category = models.CharField(max_length=20, choices=[('GOOD CUSTOMER','GOOD CUSTOMER'),('IN DEFAULT','IN DEFAULT'),('IN RECOVERY','IN RECOVERY'),('HAS A BAD LOAN','HAS A BAD LOAN'),('BLACKLISTED','BLACKLISTED')], default='GOOD CUSTOMER', null=True, blank=True)
    
class UserProfileUpload(models.Model):
    UPLOAD_TYPE_CHOICES = [('RECORD','RECORD')]
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='userprofile_uploads')
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPE_CHOICES, default='', null=True, blank=True)
    upload_file = models.FileField(upload_to='uploads/', null=True, blank=True)
    upload_file_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    processed = models.BooleanField(default=False)

class ClientUpload(models.Model):
    UPLOAD_TYPE_CHOICES = [('PROFILE_PIC','PROFILE_PIC'),('NID','NID'),('PASSPORT','PASSPORT'),
    ('DRIVERS_LICENSE','DRIVERS_LICENSE'),('SUPER_ID','SUPER_ID'),
    ('WORK_ID','WORK_ID'),('PAYSLIP','PAYSLIP'),
    ('BANK_STATEMENT','BANK_STATEMENT'),('LOAN_STATEMENT','LOAN_STATEMENT'),
    ('BANK_STANDING_ORDER','BANK_STANDING_ORDER'),
    ('TIN_CERTIFICATE','TIN_CERTIFICATE'),('LOGO','LOGO'),('IPA_CERTIFICATE','IPA_CERTIFICATE'),
    ('CASH_FLOW','CASH_FLOW'),
    ('OTHERS','OTHERS')
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_uploads')
    upload_type = models.CharField(max_length=20, choices=UPLOAD_TYPE_CHOICES, default='', null=True, blank=True)
    upload_file = models.FileField(upload_to='uploads/', null=True, blank=True)
    upload_file_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)

class ClientAddress(models.Model):
    PROVINCE_CHOICES = [('AROB','AROB'),('CENTRAL','CENTRAL'),('ENGA','ENGA'),('EAST SEPIK','EAST SEPIK'),('EHP','EHP'),('ENB','ENBP'),
    ('HELA','HELA'), ('JIWAKA','JIWAKA'),('MADANG','MADANG'),('MANUS','MANUS'),('MOROBE', 'MOROBE'),('NCD','NCD'),('NEW IRELAND','NEW IRELAND'),('ORO','ORO'),
    ('SHP','SHP'),('SIMBU','SIMBU'), ('WESTERN','WESTERN'), ('WEST SEPIK','WEST SEPIK'), ('WHP','WHP'), ('WNB','WNBP'),
    ]

    ADDRESS_TYPE_CHOICES = [('RESIDENTIAL','RESIDENTIAL'),('POSTAL','POSTAL'),('BUSINESS','BUSINESS'),('OTHERS','OTHERS')]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_address')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPE_CHOICES, default='', null=True, blank=True)
    address = models.TextField(max_length=255, null=True, blank=True)
    residential_province = models.CharField(max_length=20, choices=PROVINCE_CHOICES, null=True, blank=True, default="Not Specified")
    resident_owner = models.CharField(max_length=10, choices=[('SELF','SELF'),('RELATIVES','RELATIVES'),('RENTAL','RENTAL'),('WORK-HOUSE','WORK_HOUSE'),('OTHERS','OTHERS')], default='',null=True, blank=True)

class ClientContact(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_contact')

    email1 = models.EmailField(null=True, blank=True)
    email2 = models.EmailField(null=True, blank=True)
    mobile1 = models.IntegerField(null=True, blank=True)
    mobile2 = models.IntegerField(null=True, blank=True)
    
class ClientEmployer(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #employer information
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_employer', null=True, blank=True,)
    sector  = models.CharField(max_length=10, choices=[('PUBLIC','PUBLIC'),('PRIVATE','PRIVATE'),('SOE','SOE'),('SME','SME'),('NGO','NGO'),('OTHERS','OTHERS')], default='NA', null=True, blank=True)
    employer = models.CharField(max_length=50,null=True, blank=True, default='')
    job_title = models.CharField(max_length=255,null=True, blank=True, default='')
    work_id_number = models.CharField(max_length=20, null=True, blank=True)
    office_address = models.TextField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    pay_frequency = models.CharField(max_length=100, choices=[('FN','FORTNIGHTLY'),('MN','MONTHLY')], default='FN', null=True, blank=True)
    last_paydate = models.DateField(null=True, blank=True)
    gross_pay = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)

    work_phone = models.CharField(max_length=20, blank = True, null=True)
    work_email = models.EmailField(verbose_name='Work Email Address', max_length=50, blank = True, null=True)

class ClientBankAccount(models.Model):
    BANK_CHOICES = [('BSP', 'BSP'),('KINA','KINA'),
    ('WESTPAC','WESTPAC'),('CREDIT BANK','CREDIT BANK'),('TISA BANK','TISA BANK')
    ]
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #bankaccount info
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_bankaccount', null=True, blank=True,)
    bank = models.CharField(max_length=30, choices=BANK_CHOICES, default='', null=True, blank=True)
    account_name =  models.CharField(max_length=100, null=True, blank=True, default='')
    account_number = models.CharField(max_length=30,null=True, blank = True)
    branch_bsb = models.CharField(max_length=30,null=True, blank = True, default='')
    branch_name = models.CharField(max_length=30,null=True, blank = True, default='')

class Payslip(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    #payslip info
    
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='client_payslip', null=True, blank=True,)
    employer = models.ForeignKey(ClientEmployer, on_delete=models.CASCADE, related_name='employer_payslip', null=True, blank=True,)
    pay_frequency = models.CharField(max_length=2, choices=[('FN','FORTNIGHTLY'),('MN','MONTHLY')], default='FN', null=True, blank=True)
    last_paydate = models.DateField(null=True, blank=True)

    gross_pay = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)
    total_deductions = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)
    net_pay = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, default=0)

    pay_slip = models.FileField(upload_to='uploads/', null=True, blank=True)
    pay_slip_url = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)