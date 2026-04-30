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

