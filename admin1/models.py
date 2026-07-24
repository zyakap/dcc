from django.db import models
from users.models import UserProfile

# Create your models here.

class DelistRequest(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    name_of_requester = models.CharField(max_length=255)
    email_of_requester = models.EmailField()
    phone_of_requester = models.CharField(max_length=20)
    reason = models.TextField()
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='approved_by', null=True, blank=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)
    feedback_date = models.DateTimeField(null=True, blank=True)
    is_feedbacked = models.BooleanField(default=False)
    is_delisted = models.BooleanField(default=False)
    
    def __str__(self):
        return f'{self.name_of_requester}-{self.email_of_requester}'

class DelistRequestFeedback(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    delist_request = models.ForeignKey(DelistRequest, on_delete=models.CASCADE)
    feedback = models.TextField()
    
    def __str__(self):
        return f'{self.profile.user.email} - {self.delist_request.name_of_requester}'

class Subscriber(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    
    def __str__(self):
        return self.email

    
class DefaultListSubmission(models.Model):
    date = models.DateTimeField(auto_now_add=True)
    business_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)   
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    business_address = models.TextField(null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    submission_spreadsheet = models.FileField(upload_to='default_list_submissions')
    submission_spreadsheet_url = models.CharField(max_length=255, null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='approved_by_default', null=True, blank=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(null=True, blank=True)
    feedback_date = models.DateTimeField(null=True, blank=True)
    is_feedbacked = models.BooleanField(default=False)



# ---------------------------------------------------------------------------
# Verification workflow — for non-Loanmasta uploaded records
# ---------------------------------------------------------------------------

class RecordUploadBatch(models.Model):
    """Tracks each Excel upload from a non-Loanmasta lender or DCC staff."""
    STATUSES = [
        ('PROCESSING', 'Processing'),
        ('PENDING_REVIEW', 'Pending Review'),
        ('PARTIALLY_VERIFIED', 'Partially Verified'),
        ('COMPLETED', 'Completed'),
    ]
    uploaded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True,
                                    related_name='upload_batches')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='upload_batches/', null=True, blank=True)
    record_count = models.PositiveIntegerField(default=0)
    verified_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUSES, default='PENDING_REVIEW')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f'Batch {self.pk} — {self.uploaded_by} ({self.uploaded_at:%Y-%m-%d})'


class VerificationCase(models.Model):
    """One case per uploaded ClientProfile needing DCC verification."""
    STATUS_CHOICES = [
        ('PENDING',   'Pending Assignment'),
        ('CONTACTED', 'Borrower Contacted'),
        ('WAITING',   'Awaiting Response'),
        ('VERIFIED',  'Verified — Admitted'),
        ('REJECTED',  'Rejected — Not Admitted'),
        ('HOLD',      'On Hold'),
    ]
    CONTACT_METHODS = [
        ('EMAIL',      'Email'),
        ('PHONE',      'Phone Call'),
        ('SMS',        'SMS'),
        ('IN_PERSON',  'In Person'),
        ('LETTER',     'Physical Letter'),
    ]
    client = models.OneToOneField('client.ClientProfile', on_delete=models.CASCADE,
                                  related_name='verification_case')
    batch = models.ForeignKey(RecordUploadBatch, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='cases')
    lender = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='verification_cases')
    assigned_to = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_verifications')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contact_at = models.DateTimeField(null=True, blank=True)
    last_contact_method = models.CharField(max_length=12, choices=CONTACT_METHODS, blank=True)
    internal_notes = models.TextField(blank=True)
    lender_feedback = models.TextField(blank=True)
    lender_notified = models.BooleanField(default=False)
    lender_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'VC-{self.pk} {self.client}'


class VerificationContact(models.Model):
    """Log of every contact attempt within a VerificationCase."""
    case = models.ForeignKey(VerificationCase, on_delete=models.CASCADE,
                             related_name='contact_attempts')
    contacted_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True,
                                     related_name='contact_attempts')
    method = models.CharField(max_length=12, choices=VerificationCase.CONTACT_METHODS)
    contacted_at = models.DateTimeField(auto_now_add=True)
    outcome = models.CharField(max_length=50, blank=True,
                               help_text='e.g. answered, no reply, confirmed, denied')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-contacted_at']


# ---------------------------------------------------------------------------
# Debt settlement / brokerage
# ---------------------------------------------------------------------------

class DebtSettlement(models.Model):
    """DCC brokers a settlement between a lender and a borrower in default."""
    STATUS_CHOICES = [
        ('OPEN',         'Open — Assessing'),
        ('NEGOTIATING',  'Actively Negotiating'),
        ('OFFER_MADE',   'Settlement Offer Made'),
        ('ACCEPTED',     'Offer Accepted'),
        ('REJECTED',     'Offer Rejected'),
        ('SETTLED',      'Settled — Paid / Agreed'),
        ('CLOSED',       'Closed — No Resolution'),
    ]
    client = models.ForeignKey('client.ClientProfile', on_delete=models.CASCADE,
                               related_name='settlements')
    lender = models.ForeignKey(UserProfile, on_delete=models.CASCADE,
                               related_name='settlements_initiated')
    assigned_dcc_officer = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True,
                                             blank=True, related_name='brokered_settlements')
    default_notice = models.ForeignKey('client.DefaultNotice', on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name='settlements')
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    offered_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    agreed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='OPEN')
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    target_settlement_date = models.DateField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    settlement_doc = models.FileField(upload_to='settlements/', null=True, blank=True)
    notes = models.TextField(blank=True)

    # Borrower contact info (may not have a BorrowerAccount)
    borrower_email = models.EmailField(blank=True)
    borrower_phone = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f'DS-{self.pk} {self.client} vs {self.lender}'


class SettlementMessage(models.Model):
    """Threaded message log within a DebtSettlement case."""
    SENDER_TYPES = [
        ('DCC',      'DCC Officer'),
        ('LENDER',   'Lender'),
        ('BORROWER', 'Borrower'),
        ('SYSTEM',   'System'),
    ]
    settlement = models.ForeignKey(DebtSettlement, on_delete=models.CASCADE,
                                   related_name='messages')
    sender_type = models.CharField(max_length=10, choices=SENDER_TYPES)
    sender_name = models.CharField(max_length=100, blank=True)
    body = models.TextField()
    attachment = models.FileField(upload_to='settlement_msgs/', null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    is_internal = models.BooleanField(default=False,
                                      help_text='Internal DCC notes — not visible to lender/borrower')

    class Meta:
        ordering = ['sent_at']
