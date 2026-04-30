from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import UserProfile

from .widgets import DatePickerInput

User = get_user_model()

class RegisterForm(forms.ModelForm):
    
    """
    The default
    
    """
    
    password1 = forms.CharField(label='Password',widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    
    class Meta:
        model = User
        fields = ['email']
        
    def clean_email(self):
        '''
        Verify email is available.
        '''
        
        email = self.cleaned_data.get('email')
        qs = User.objects.filter(email=email)
        if qs.exists():
            raise forms.ValidationError('Email already exists!')
        return email
    
    def clean(self):
        '''
        Verify both passwords match.
    
        '''
        
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 is not None and password1 != password2:
            self.add_error("password2", "Your passwords must match")
        return cleaned_data

    def save(self, commit=True):
        #save the provided password in hashed format
        
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
    
class UserAdminCreationForm(forms.ModelForm):
    """ 
    A form for creating. Includes all the required fields, plus a repeated password.
    """
    
    password1 = forms.CharField(label='Password',widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['email','active', 'admin', 'confirmed', 'defaulted', 'suspended','dcc_flagged', 'cdb_flagged']
    
    
    def clean(self):
        '''
        Verify both passwords match.
        '''
        
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        
        if password1 is not None and password1 != password2:
            self.add_error("password2", "Your passwords must match")
        return cleaned_data
    
    def save(self, commit=True):
        #save the provided password in hashed format
        
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
        
class UserAdminChangeForm(forms.ModelForm):
    
    """
    A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    password hash display field.
    """
    
    password = ReadOnlyPasswordHashField()
    
    class Meta:
        model = User
        fields = ['email', 'password', 'active', 'admin', 'confirmed', 'defaulted', 'suspended','dcc_flagged', 'cdb_flagged']
        
    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        
        return self.initial["password"]
    
    
class LoginForm(forms.Form):
    
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),)
    

class PasswordResetForm(forms.Form):
    
    email = forms.EmailField()
        
class UserProfileForm(forms.ModelForm):
    
    class Meta:
        model = UserProfile
        fields = '__all__'
        exclude = ['user','id']
        
class ContactInfoForm(forms.ModelForm):
    
    class Meta:
        model = UserProfile
        fields =['first_name','middle_name', 'last_name', 'role', 'email' ,'mobile1']
 


      

class OrganisationInfoUpdateForm(forms.ModelForm):
    
    class Meta:
        model = UserProfile
        fields = ['sector','organisation','office_address','work_phone', 'work_email', 'ipa_number', 'tin_number']

class BusinessUploadForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['ipa', 'tin']
