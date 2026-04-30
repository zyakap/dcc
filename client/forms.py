# forms.py
from django import forms
from .models import ClientProfile, BusinessProfile
from .widgets import DatePickerInput

class ClientProfileForm(forms.ModelForm):
    class Meta:
        model = ClientProfile
        fields = '__all__'
        exclude = ['user','uid','luid','category','type_of_customer',
                   'activation','credit_rating','personal_interest_rate','credit_consent','terms_consent',
                   'created_at','updated_at',
                   'work_id_url', 'nid_url', 'passport_url', 'drivers_license_url', 'super_id_url',
                   'repayment_limit', 'dcc_comment', 'cdb_comment',
                   'number_of_loans',
                   ]
        
        widgets = {
            'date_of_birth' : DatePickerInput(),
            'start_date': DatePickerInput(), 
            'last_paydate': DatePickerInput(),
            } 

class BusinessProfileForm(forms.ModelForm):
    class Meta:
        model = BusinessProfile
        fields = '__all__'
        exclude = ['ref','ipa_certificate_url','tin_certificate_url','cash_flow_url','bank_statement_url','bank_standing_order_url', 
                   'location_pic_url','created_at','updated_at','dcc_comment','cdb_comment']