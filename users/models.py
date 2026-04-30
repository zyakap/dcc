from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.forms import DecimalField, FileField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, username=None, is_active=False, is_confirmed=False, is_dcc_flagged=False, is_cdb_flagged=False):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
        )

        user.set_password(password)
        user.username = username
        user.active = is_active
        user.confirmed = is_confirmed
       
        user.dcc_flagged = is_dcc_flagged
        user.cdb_flagged = is_cdb_flagged
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email and password.
        """
        username_ = email.split('@')[0]

        user = self.create_user(
            email,
            username=username_,
            password=password,
        )

        username_ = email.split('@')[0]
        user.username = username_

        user.staff = True
        user.admin = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    
    email = models.EmailField(
        verbose_name='email address',
        max_length=255,
        unique=True,
    )
    username = models.CharField(verbose_name='username', max_length=20, unique=True)
    active = models.BooleanField(default=False)
    staff = models.BooleanField(default=False) # a admin user; non super-user
    admin = models.BooleanField(default=False) # a superuser
    updated_at = models.DateTimeField(auto_now=True)
    confirmed = models.BooleanField(default=False)
    defaulted = models.BooleanField(default=False)
    suspended = models.BooleanField(default=False)
    dcc_flagged = models.BooleanField(default=False)
    cdb_flagged = models.BooleanField(default=False)
    
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    
    objects = UserManager()
    
    # notice the absence of a "Password field", that is built in.

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # Email & Password are required by default.

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        # The user is identified by their email address
        return self.email

    def get_short_name(self):
        # The user is identified by their email address
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        return self.staff

    @property
    def is_admin(self):
        "Is the user a admin member?"
        return self.admin

    @property
    def is_confirmed(self):
        return self.is_confirmed
    
    @property
    def is_defaulted(self):
        return self.defaulted

    @property
    def is_suspended(self):
        return self.suspended
    
    @property
    def is_dcc_flagged(self):
        return self.dcc_flagged

    @property
    def is_cdb_flagged(self):
        return self.cdb_flagged

    def email_user(self, *args, **kwargs):
        send_mail(
        '{}'.format(args[0]),
        '{}'.format(args[1]),
        'dev@webmasta.com.pg',
        [self.email],
        fail_silently=False,
    )

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    LUID = models.CharField(max_length=55)
    endpoint = models.CharField(max_length=255, default='www.loanmasta.com')
    category = models.CharField(max_length=20, choices=[('SOLE TRADER','SOLE TRADER'),('SME','SME'),('COMPANY','COMPANY')], default='nonmember', null=True, blank=True)
    date_joined = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    #contact person
    title = models.CharField(max_length=6, choices=[('Mr','Mr'),('Mrs','Mrs'), ('Dr','Dr'),('Miss','Miss')], default='', null=True, blank=True)
    first_name = models.CharField(max_length=55)
    middle_name = models.CharField(max_length=55, null=True, blank=True)
    last_name = models.CharField(max_length=55, null=True, blank=True)
    role = models.CharField(max_length=55, null=True, blank=True)
    #contact
    email = models.EmailField(null=True, blank = True)
    mobile1 = models.IntegerField(null=True, blank = True)
    mobile2 = models.IntegerField(null=True, blank = True)
    
    #busines info
    
    ipa = models.FileField('IPA CERTIFICATE:', upload_to='ids/',null=True, blank=True)
    ipa_number = models.CharField(max_length=255, null=True, blank=True)
    ipa_url = models.CharField(max_length=555, null=True, blank=True)
    tin = models.FileField('TIN CERTIFICATE:', upload_to='ids/',null=True, blank=True)
    tin_number = models.CharField(max_length=255, null=True, blank=True)
    tin_url = models.CharField(max_length=555, null=True, blank=True)
    
    #organisation information
    sector = models.CharField(max_length=10, null=True, blank=True, choices=[('PUBLIC','PUBLIC'),('PRIVATE','PRIVATE')])
    organisation = models.CharField(max_length=110,null=True, blank=True)
    office_address = models.CharField(max_length=255, null=True, blank=True)
    work_phone = models.IntegerField(blank = True, null=True )
    work_email = models.EmailField(verbose_name='work email address', max_length=55, unique=True, blank = True, null=True)
    
    initials = models.CharField(max_length=10, null=True, blank=True)
    use_loanmasta = models.BooleanField(default=False)

    record_count = models.IntegerField(default=0)
    
    def __str__(self):
        if self.category == 'SOLE TRADER':
            return f'ST - {self.first_name} {self.last_name}'
        else:
            return self.organisation


class ActivityLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    


    