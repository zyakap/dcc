from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.forms import DecimalField, FileField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.db import models
from users.models import UserProfile


class _AuditedModel(models.Model):
    """Abstract mixin: on every save(), diffs this instance's tracked fields
    against what is currently in the database and appends any change to
    ClientProfileHistory — the single audit trail for everything DCC knows
    about a client, across every tenant that has ever fed data about them.

    This is deliberately a database-diff on save(), not a signal on the
    incoming tenant feed, so it also captures direct edits made by DCC staff
    (e.g. via /appadmin/), not just tenant-sync writes. The very first save()
    of a row is logged too (old_value=None), so "the first copy" of a fact is
    preserved exactly like every value after it — nothing is only ever
    overwritten in place.
    """
    _history_excluded_fields = ('id', 'created_at', 'updated_at')
    _history_prefix = ''

    class Meta:
        abstract = True

    def _history_client(self):
        """The ClientProfile this instance's history rows belong to."""
        if isinstance(self, ClientProfile):
            return self
        return getattr(self, 'client', None)

    def save(self, *args, _history_source='MANUAL', **kwargs):
        old = None
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
        super().save(*args, **kwargs)
        self._record_history(old, source=_history_source)

    def _record_history(self, old, source='MANUAL'):
        client = self._history_client()
        if client is None or client.pk is None:
            return
        entries = []
        for f in self._meta.fields:
            name = f.name
            if name in self._history_excluded_fields:
                continue
            new_val = getattr(self, name)
            old_val = getattr(old, name) if old is not None else None
            new_str = '' if new_val in (None, '') else str(new_val)
            old_str = '' if old_val in (None, '') else str(old_val)
            if new_str == old_str:
                continue
            if old is None and not new_str:
                continue  # nothing worth recording on creation if left blank
            entries.append(ClientProfileHistory(
                client=client,
                field_name=f'{self._history_prefix}{name}',
                old_value=old_str or None,
                new_value=new_str or None,
                source=source,
            ))
        if entries:
            ClientProfileHistory.objects.bulk_create(entries)


class ClientProfile(_AuditedModel):

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

    # A client keeps exactly one profile per tenant (LUID) — re-registering or
    # re-syncing must update that same row, never create a duplicate.
    class Meta:
        unique_together = [('LUID', 'CUID')]

    _history_excluded_fields = ('id', 'created_at', 'updated_at', 'user_profile')

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


class ClientProfileHistory(models.Model):
    """Full audit trail for one tenant's copy of a client. Every fact DCC has
    ever held about this ClientProfile (or its ClientEmployer / ClientBankAccount
    rows) gets one entry per change — the very first value included, not just
    edits — so nothing is ever only overwritten in place. See _AuditedModel."""
    SOURCE_CHOICES = [
        ('SYNC', 'Tenant Sync'),
        ('MANUAL', 'DCC Staff'),
        ('SYSTEM', 'System'),
    ]

    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE, related_name='history')
    field_name = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='SYNC')

    class Meta:
        ordering = ['-changed_at']
        indexes = [models.Index(fields=['client', '-changed_at'])]
        verbose_name_plural = 'Client profile history'

    def __str__(self):
        return f'{self.client} · {self.field_name}: {self.old_value!r} → {self.new_value!r}'


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
    
class ClientCreditScore(models.Model):
    """Computed credit score for a client based on all loan/transaction history
    across every DCC tenant. Recomputed each time a credit check is paid for."""
    GRADE_CHOICES = [
        ('AAA', 'AAA – Exceptional'),
        ('AA',  'AA – Excellent'),
        ('A',   'A – Very Good'),
        ('BBB', 'BBB – Good'),
        ('BB',  'BB – Fair'),
        ('B',   'B – Below Average'),
        ('CCC', 'CCC – Poor'),
        ('CC',  'CC – Bad'),
        ('C',   'C – Very Bad'),
    ]
    client = models.OneToOneField(ClientProfile, on_delete=models.CASCADE, related_name='credit_score')
    score = models.PositiveIntegerField(default=500, help_text='0–1000 composite credit score.')
    grade = models.CharField(max_length=5, choices=GRADE_CHOICES, default='BBB')
    computed_at = models.DateTimeField(auto_now=True)
    # factor breakdown (stored for display / audit)
    total_loans = models.IntegerField(default=0)
    completed_loans = models.IntegerField(default=0)
    active_loans = models.IntegerField(default=0)
    defaulted_loans = models.IntegerField(default=0)
    arrears_loans = models.IntegerField(default=0)
    recovery_loans = models.IntegerField(default=0)
    total_borrowed = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_outstanding = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.client} – {self.grade} ({self.score}/1000)'

    @staticmethod
    def _score_to_grade(score):
        if score >= 850: return 'AAA'
        if score >= 750: return 'AA'
        if score >= 650: return 'A'
        if score >= 550: return 'BBB'
        if score >= 450: return 'BB'
        if score >= 350: return 'B'
        if score >= 250: return 'CCC'
        if score >= 150: return 'CC'
        return 'C'

    def recompute(self):
        """Recalculate score from live loan/transaction data across all tenants
        and save. Call after each paid credit-check access event."""
        from loan.models import Loan
        from django.db.models import Sum as _Sum

        # Gather all loan records for this client (across all lender tenants)
        loans = Loan.objects.filter(owner=self.client)
        total = loans.count()
        completed = loans.filter(status='COMPLETED').count()
        active = loans.filter(funded_category='ACTIVE').count()
        defaulted = loans.filter(status='DEFAULTED').count()
        arrears = loans.filter(funded_category='ACTIVE', total_arrears__gt=0).count()
        recovery = loans.filter(funded_category='RECOVERY').count()
        total_borrowed = loans.aggregate(s=_Sum('amount'))['s'] or 0
        total_outstanding = loans.aggregate(s=_Sum('total_outstanding'))['s'] or 0

        # Base score
        score = 500
        # Positive: completed loans, history depth
        score += min(completed * 30, 150)
        if total > 0:
            tenure_years = (loans.order_by('funding_date').last().funding_date -
                            loans.order_by('funding_date').first().funding_date).days // 365 if \
                loans.filter(funding_date__isnull=False).count() >= 2 else 0
            score += min(tenure_years * 10, 50)
        # Negative: bad loan behaviour
        score -= defaulted * 150
        score -= arrears * 50
        score -= recovery * 100
        # DCC flags
        if self.client.dcc_flagged:
            score -= 100
        if self.client.dcc_status in ('DEFAULT', 'BAD'):
            score -= 80
        if self.client.dcc_status == 'RECOVERY':
            score -= 60
        if self.client.public_category == 'BLACKLISTED':
            score = min(score, 49)

        score = max(0, min(1000, score))

        self.score = score
        self.grade = self._score_to_grade(score)
        self.total_loans = total
        self.completed_loans = completed
        self.active_loans = active
        self.defaulted_loans = defaulted
        self.arrears_loans = arrears
        self.recovery_loans = recovery
        self.total_borrowed = total_borrowed
        self.total_outstanding = total_outstanding
        self.save()


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
    
class ClientEmployer(_AuditedModel):
    _history_prefix = 'employer.'
    _history_excluded_fields = ('id', 'created_at', 'updated_at', 'client')

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

class ClientBankAccount(_AuditedModel):
    _history_prefix = 'bank.'
    _history_excluded_fields = ('id', 'created_at', 'updated_at', 'client')

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