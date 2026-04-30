from django.conf import settings
from django.shortcuts import render
from datetime import datetime

import requests
from .models import ClientProfile, BusinessProfile, ClientContact, ClientAddress, ClientEmployer, ClientBankAccount, ClientUpload
from .serializers import ClientProfileSerializer  # Import your LoanSerializer
from .functions import fileuploader, fileuploader_records, login_check, admin_check, check_staff
# views.py
from django.shortcuts import render, redirect
from django.core.files.storage import FileSystemStorage
from django.contrib import messages
from django.urls import reverse
from .forms import ClientProfileForm, BusinessProfileForm
from users.models import UserProfile
from django.template.loader import render_to_string
from admin1.models import DefaultListSubmission

#to send email
from django.conf import settings

from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.html import strip_tags


from datetime import date, timedelta

today = date.today()
yesterday = today - timedelta(days=1)


def get_clientprofiles(request, endpoint_url):

    endpoint = f'https://{ endpoint_url }/api/profiles/'
    # Make a GET request to the API endpoint
    response = requests.get(endpoint, verify=False)
    # Check if the request was successful
    if response.status_code == 200:
        # Extract JSON data from the response
        data = response.json()
        print(data)
        # Check if 'results' key exists in the data
        if data:
            # Use LoanSerializer to deserialize the data into Loan instances
            serializer = ClientProfileSerializer(data=data, many=True)
            # Check if deserialization was successful
            if serializer.is_valid():
                # Save deserialized data into Loan instances
                serializer.save()
                # Retrieve the Loan instances from the database
                #clients = ClientProfile.objects.filter(vetted=True)
                clients = ClientProfile.objects.all()

                # Now you have the loans data, you can pass it to the template
                return render(request, 'client_list.html', {'clients': clients})
            else:
                # Print serializer errors
                print("Serializer errors:", serializer.errors)
                # Handle error if deserialization failed
                error_message = "Failed to deserialize data from the API"
                return render(request, 'error.html', {'error_message': error_message})
        else:
            # Handle error if 'results' key is not found in the data
            error_message = "No New Clients found"
            return render(request, 'error.html', {'error_message': error_message})
    else:
        # Handle error if the request was not successful
        error_message = "Failed to fetch data from the API"
        return render(request, 'error.html', {'error_message': error_message})

def client_record_detail(request, client_id):
    client = ClientProfile.objects.get(id=client_id)
    loans = Loan.objects.filter(owner=client)
    
    return render(request, 'client_record_detail.html', {'nav': 'client_record_detail', 'client': client,'loans': loans})

def client_record_detail_sample(request):
    
    return render(request, 'client_record_detail.html', {'nav': 'client_record_detail_sample'})

def business_record_detail(request, business_id):
    business = BusinessProfile.objects.get(id=business_id)
    return render(request, 'business_record_detail.html', {'nav': 'business_record_detail', 'business': business})

def business_record_detail_sample(request):
    
    return render(request, 'business_record_detail.html', {'nav': 'business_record_detail_sample'})

def add_client(request):

    userprofile = UserProfile.objects.get(user=request.user)
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        mobile1 = request.POST.get('mobile1')

        first_name_initial = first_name[0:2].upper()
        last_name_initial = last_name[0:2].upper()
        inital_dcc = f'DCC{first_name_initial}{last_name_initial}'
        
        #for now, let everyone enter their own record
        '''
        if ClientProfile.objects.filter(first_name=first_name, last_name=last_name).exists():
            if ClientProfile.objects.filter(first_name=first_name, last_name=last_name).inital_dcc == inital_dcc:
                return redirect('client_detail', ClientProfile.objects.get(first_name=first_name, last_name=last_name).id)
        '''

        client_profile = ClientProfile.objects.create(
            user_profile=userprofile,
            first_name=first_name,
            last_name=last_name)
        client_profile.save()

        if request.POST.get('middle_name'):
            client_profile.middle_name = request.POST.get('middle_name')
        if request.POST.get('nick_name'):
            client_profile.nick_name = request.POST.get('nick_name')
        if request.POST.get('other_names'):
            client_profile.other_names = request.POST.get('other_names')
        if request.POST.get('gender'):
            client_profile.gender = request.POST.get('gender')
        if request.POST.get('date_of_birth'):
            client_profile.date_of_birth = request.POST.get('date_of_birth')
        if request.POST.get('marital_status'):
            client_profile.marital_status = request.POST.get('marital_status')

        if request.POST.get('email'):
            client_profile.email = request.POST.get('email')
        if request.POST.get('mobile1'):
            client_profile.mobile1 = request.POST.get('mobile1')
        
        if request.POST.get('place_of_origin'):
             client_profile.place_of_origin = request.POST.get('place_of_origin')
        if request.POST.get('province_of_origin'):
             client_profile.province_of_origin = request.POST.get('province_of_origin')

        client_profile.save()

        contact_check = []
        address_check = []
        employment_check = []
        bank_check = []

        #contact_checks
        if request.POST.get('email'):
            client_profile.email = request.POST.get('email')
            contact_check.append('EMAIL')
        if request.POST.get('email1'):
            client_profile.email1 = request.POST.get('email1')

            contact_check.append('EMAIL1')
        if request.POST.get('mobile1'):
            client_profile.mobile1 = request.POST.get('mobile1')
            contact_check.append('MOBILE1')
        if request.POST.get('mobile2'):
            mobile2 = request.POST.get('mobile2')
            contact_check.append('MOBILE2')
        
        #address_Checks
        if request.POST.get('address'):
            address = request.POST.get('address')
            address_check.append('ADDRESS')
        if request.POST.get('residential_province'):
            residential_province = request.POST.get('residential_province')
            address_check.append('RESIDENTIAL_PROVINCE')
        if request.POST.get('resident_owner'):
            resident_owner = request.POST.get('resident_owner')
            address_check.append('RESIDENT_OWNER')  
        
        #employment_Checks
        if request.POST.get('sector'):
            sector = request.POST.get('sector')
            employment_check.append('SECTOR')
        if request.POST.get('employer'):
            employer = request.POST.get('employer')
            employment_check.append('EMPLOYER')
        if request.POST.get('job_title'):
            job_title = request.POST.get('job_title')
            employment_check.append('JOB_TITLE')
        if request.POST.get('office_address'):
            office_address = request.POST.get('office_address')
            employment_check.append('OFFICE_ADDRESS')
        if request.POST.get('start_date'):
            start_date = request.POST.get('start_date')
            employment_check.append('START_DATE')
        if request.POST.get('pay_frequency'):
            pay_frequency = request.POST.get('pay_frequency')
            employment_check.append('PAY_FREQUENCY')
        if request.POST.get('last_paydate'):
            last_paydate = request.POST.get('last_paydate')
            employment_check.append('LAST_PAYDATE')
        if request.POST.get('gross_pay'):
            gross_pay = request.POST.get('gross_pay')
            employment_check.append('GROSS_PAY')

        if request.POST.get('work_id_number'):
            work_id_number = request.POST.get('work_id_number')
            employment_check.append('WORK_ID_NUMBER')
        
        if request.POST.get('work_phone'):
            work_phone = request.POST.get('work_phone')
            employment_check.append('WORK_PHONE')
        if request.POST.get('work_email'):
            work_email = request.POST.get('work_email')
            employment_check.append('WORK_EMAIL')
        
        #bank_checks
        if request.POST.get('bank'):
            bank = request.POST.get('bank')
            bank_check.append('BANK')
        if request.POST.get('bank_account_name'):
            bank_account_name = request.POST.get('bank_account_name')
            bank_check.append('BANK_ACCOUNT_NAME')
        if request.POST.get('bank_account_number'):
            bank_account_number = request.POST.get('bank_account_number')
            bank_check.append('BANK_ACCOUNT_NUMBER')
        if request.POST.get('bank_branch_bsb'):
            bank_branch_bsb = request.POST.get('bank_branch_bsb')
            bank_check.append('BANK_BRANCH_BSB')
        if request.POST.get('bank_branch_name'):
            bank_branch_name = request.POST.get('bank_branch_name')
            bank_check.append('BANK_BRANCH_NAME')

        #client Profile update
        if request.POST.get('nid_number'):
             client_profile.nid_number = request.POST.get('nid_number')
        if request.POST.get('passport_number'):
             client_profile.passport_number = request.POST.get('passport_number')
        if request.POST.get('drivers_license_number'):
             client_profile.drivers_license_number = request.POST.get('drivers_license_number')
        if request.POST.get('super_member_code'):
             client_profile.super_member_code = request.POST.get('super_member_code')
        #dcc updates
        if request.POST.get('has_loan'):
            client_profile.has_loan = True
        
        if request.POST.get('dcc_flagged'):
            client_profile.dcc_flagged = True
        if request.POST.get('dcc_Status') is not 'SELECT STATUS':
            client_profile.dcc_status = request.POST.get('dcc_Status')
        if request.POST.get('public_listing'):
            client_profile.public_listing = True
        #comments
        if request.POST.get('dcc_comment'):
            client_profile.dcc_comment = request.POST.get('dcc_comment')
        if request.POST.get('cdb_comment'):
            client_profile.cdb_comment = request.POST.get('cdb_comment')
        if request.POST.get('notes'):
            client_profile.notes = request.POST.get('notes')
        
        if request.POST.get('credit_rating'):
            client_profile.credit_rating = request.POST.get('credit_rating')
        if request.POST.get('number_of_loans'):
            client_profile.number_of_loans = request.POST.get('number_of_loans')
        if request.POST.get('repayment_limit'):
            client_profile.repayment_limit = request.POST.get('repayment_limit')
        client_profile.save()

        #entry creation
        if contact_check:
            clientcontact = ClientContact.objects.create(client=client_profile)
            for item in contact_check:
                item_db_name = item.lower()
                setattr(clientcontact, item_db_name, request.POST.get(item_db_name))
            clientcontact.save()
        
        if bank_check:
            clientbank = ClientBankAccount.objects.create(client=client_profile)
            for item in bank_check:
                item_db_name = item.lower()
                setattr(clientbank, item_db_name, request.POST.get(item_db_name))
            clientbank.save()

        if address_check:
            clientaddress = ClientAddress.objects.create(client=client_profile)
            for item in address_check:
                item_db_name = item.lower()
                setattr(clientaddress, item_db_name, request.POST.get(item_db_name))
            clientaddress.save()
        
        if employment_check:
            clientemployment = ClientEmployer.objects.create(client=client_profile)
            for item in employment_check:
                item_db_name = item.lower()
                setattr(clientemployment, item_db_name, request.POST.get(item_db_name))
            clientemployment.save()


        #uploads
        if 'nid' in request.FILES:
            fileuploader(request, 'nid', client_profile)
        if 'passport' in request.FILES:
            fileuploader(request, 'passport', client_profile)
        if 'drivers_license' in request.FILES:
            fileuploader(request, 'drivers_license', client_profile)
        if 'super_id' in request.FILES:
            fileuploader(request, 'super_id', client_profile)
        if 'work_id' in request.FILES:
            fileuploader(request, 'work_id', client_profile)
        
        # Assuming you have access to the user and luid in your view
        uid = request.user.id  # or however you get the user ID
        first_name_initial = first_name[0:2].upper()
        last_name_initial = last_name[0:2].upper()
        if request.POST.get('gender'):
            gender = request.POST.get('gender')
            gender_initial = gender[0].upper()
        else:
            gender_initial = 'X'
        
        # Assuming dob is a string in the format 'YYYY-MM-DD'
        if request.POST.get('date_of_birth'):
            date_of_birth = request.POST.get('date_of_birth')
            dob = date_of_birth
            dob_datetime = datetime.strptime(dob, '%Y-%m-%d')
            dob_formatted = dob_datetime.strftime('%d%m%y')
        else:
            dob_formatted = '000000'

        uid_init = f'{first_name_initial}{last_name_initial}{gender_initial}{dob_formatted}'
        
        if request.POST.get('nid_number'):
            nid_number = request.POST.get('nid_number')
            nid_suffix = nid_number[-4:]
            uid = f'{uid_init}{nid_suffix}'
        else:
            uid = f'{uid_init}0000'
        
        luid = settings.LUID
        prefix = settings.PREFIX
        client_profile.luid = f'{prefix}{luid}'
        client_profile.uid = uid
        client_profile.save()

        return redirect('client_detail', client_profile.id)
    context = {
        'nav': 'add_client',
        'dcc_statuses': ClientProfile.DCC_STATUS_CHOICES,
        
        'provinces': ClientAddress.PROVINCE_CHOICES,
        'address_types': ClientAddress.ADDRESS_TYPE_CHOICES,
        }
    
    return render(request, 'add_client.html', context)

def add_business(request):
    profile = UserProfile.objects.get(user=request.user)
    clients = ClientProfile.objects.filter(user_profile=profile)
    if request.method == 'POST':
        
        buid = f'{profile.uid}Bz'
        business_profile = BusinessProfile.objects.create(
            buid=buid)

        business_profile.save()

        if request.POST.get('business_owner'):
            clientprofile = ClientProfile.objects.get(id=request.POST.get('business_owner'))
            business_profile.business_owner = clientprofile
            business_profile.save()
        if request.POST.get('business_type'):
            business_profile.business_type = request.POST.get('business_type')
        if request.POST.get('category'):
            business_profile.category = request.POST.get('category')
        if request.POST.get('trading_name'):
            business_profile.trading_name = request.POST.get('trading_name')
        if request.POST.get('registered_name'):
            business_profile.registered_name = request.POST.get('registered_name')
        if request.POST.get('business_address'):
            business_profile.business_address = request.POST.get('business_address')
        if request.POST.get('email'):
            business_profile.email = request.POST.get('email')
        if request.POST.get('phone'):
            business_profile.phone = request.POST.get('phone')
        if request.POST.get('website'):
            business_profile.website = request.POST.get('website')
        if request.POST.get('ipa_registration_number'):
            business_profile.ipa_registration_number = request.POST.get('ipa_registration_number')
        if request.POST.get('tin_number'):
            business_profile.tin_number = request.POST.get('tin_number')
        if request.POST.get('business_amount'):
            business_profile.business_amount = request.POST.get('business_amount')
        if request.POST.get('date_of_committment'):
            business_profile.date_of_committment = request.POST.get('date_of_committment')
        if request.POST.get('public_listing'):
            business_profile.public_listing = True
        
        business_profile.save()
        messages.success(request, 'Business Profile created successfully')
        
        return redirect('business_records')
        
    return render(request, 'add_business.html', {'nav': 'add_business', 'clients': clients })


def upload_records(request):
    profile = UserProfile.objects.get(user=request.user)
    clients = ClientProfile.objects.filter(user_profile=profile)
    if request.method == 'POST':
        if 'client_records_data' in request.FILES:
            file_url = fileuploader_records(request, 'client_records_data', profile)
            
            DefaultListSubmission.objects.create(
          
            business_name=profile.organisation,
            contact_person = f'{profile.first_name} {profile.last_name}',
            phone=profile.mobile1,
            email=profile.email,
            business_address=profile.office_address,
            comments='Submitted',
            submission_spreadsheet_url=file_url
            )


            email_subject=f'Record Uploaded by {profile.first_name} {profile.last_name}'
            #
            
            # HTML EMAIL
            html_content = render_to_string("e_email_temp_general.html", {
                'subject': email_subject,
                'greeting': f'Hi {profile.first_name}',
                'cta': 'yes',
                'cta_btn1_label': 'Records Uploaded',
                'cta_btn1_link': f'{file_url}',
                'message': f'Kindly find attached records that were uploaded.',
                'message_details': f'Please upload and advise',
                'userprofile': profile,
                'domain': settings.DOMAIN,
               
            })
            
            #########  SENDING EMAIL  #########
            #reply to email
            reply_to_email = 'admin@dc.com.pg'
            sender = 'admin@dc.com.pg'
            cc_list = settings.CC_EMAILS
            bcc_list = settings.BCC_EMAILS
            email_list_one = ['zyakap@webmasta.com.pg']
            email_list_two = [profile.email,'info@dc.com.pg']
            
            email_list  = email_list_one + email_list_two

            text_content = strip_tags(html_content)
            email = EmailMultiAlternatives(email_subject, text_content, sender,email_list, cc=cc_list, bcc=bcc_list, reply_to=[reply_to_email])
            email.attach_alternative(html_content, "text/html")
            email.send()
            try:
                email.send()
                messages.success(request, "The file was sent to admin.", extra_tags='info')
            except:
                messages.error(request, "The file alert was NOT sent to admin.", extra_tags='danger')
                return redirect('upload_complete')

            return redirect('upload_complete')
        
        else:
            messages.error(request, 'No file selected', extra_tags='danger')

    return render(request, 'upload_records.html', {'nav': 'upload_records',})

def upload_complete(request):

    return render(request, 'upload_complete.html', {'nav': 'upload_records',})

def client_records(request):
    clients = ClientProfile.objects.filter(vetted=True)
    return render(request, 'client_records.html', {'nav':'client_records', 'clients': clients})

def client_records_under_review(request):
    clients = ClientProfile.objects.filter(vetted=False)
    return render(request, 'client_records_under_review.html', {'nav':'client_records_under_review', 'clients': clients})

def client_records_dcc(request):
    clients = ClientProfile.objects.filter(vetted=True)
    return render(request, 'client_records_dcc.html', {'nav':'client_records_dcc', 'clients': clients})

def business_records(request):
    businesses = BusinessProfile.objects.filter(vetted=True)
    return render(request, 'business_records.html', {'nav':'business_records', 'businesses': businesses})

def business_records_dcc(request):
    businesses = BusinessProfile.objects.filter(vetted=True)
    return render(request, 'business_records_dcc.html', {'nav':'business_records_dcc', 'businesses': businesses})

def recent_client_records_dcc(request):
    clients = ClientProfile.objects.filter(vetted=True)
    return render(request, 'recent_client_records.html', {'nav':'recent_client_records_dcc', 'clients': clients})

def recovery_insights(request):
    clients = ClientProfile.objects.filter(vetted=True)
    return render(request, 'recovery_insights.html', {'nav':'recovery_insights', 'clients': clients})





@admin_check
def filtered_client_records_your_records_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    clients = ClientProfile.objects.filter(user_profile=user_profile, created_at__lt=today)
    context = {
        'nav':'client_records', 
        'clients': clients,
        'count': clients.count(),
        'descriptor': 'Records created today'
        }

    return render(request, 'filtered_client_records.html', context)

@admin_check
def filtered_client_records_your_updated_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    clients = ClientProfile.objects.filter(user_profile=user_profile, updated_at__gt=today)
    context = {
        'nav':'client_records', 
        'clients': clients,
        'count': clients.count(),
        'descriptor': 'Records updated today'
        }

    return render(request, 'filtered_client_records.html', context)

@admin_check
def filtered_records_your_business_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    businesses = BusinessProfile.objects.filter(user_profile=user_profile, updated_at__lt=today)
    context = {
        'nav':'business_records', 
        'businesses': businesses,
        'count': businesses.count(),
        'descriptor': 'Business Records added today'
        }

    return render(request, 'filtered_business_records.html', context)

@admin_check
def filtered_client_records_dcc_records_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    clients = ClientProfile.objects.filter(created_at__gt=today)
    context = {
        'nav':'client_records_dcc', 
        'clients': clients,
        'count': clients.count(),
        'descriptor': 'DCC Records created today'
        }

    return render(request, 'filtered_client_records.html', context)

@admin_check
def filtered_client_records_dcc_updated_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    clients = ClientProfile.objects.filter(updated_at__gt=today)
    context = {
        'nav':'client_records_dcc', 
        'clients': clients,
        'count': clients.count(),
        'descriptor': 'DCC Records updated today'
        }

    return render(request, 'filtered_client_records.html', context)

@admin_check
def filtered_business_records_dcc_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    businesses = BusinessProfile.objects.filter(created_at__gt=today)
    context = {
        'nav':'business_records_dcc', 
        'businesses': businesses,
        'count': businesses.count(),
        'descriptor': 'DCC Business Records added today'
        }

    return render(request, 'filtered_business_records.html', context)

@admin_check
def filtered_business_records_dcc_updated_today(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    businesses = BusinessProfile.objects.filter(updated_at__gt=today)
    context = {
        'nav':'business_records_dcc', 
        'businesses': businesses,
        'count': businesses.count(),
        'descriptor': 'DCC Business Records added today'
        }

    return render(request, 'filtered_business_records.html', context)

from loan.models import Loan
from django.http import Http404
#loan records
@admin_check
def filtered_loan_records_your_arrears(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    loans = Loan.objects.filter(lender=user_profile, funded_category='ACTIVE')
    context = {
        'nav':'client_records', 
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'Loans with Arrears'
        }

    return render(request, 'filtered_loan_list.html', context)

#loan records
@admin_check
def filtered_loan_records_dcc_arrears(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    loans = Loan.objects.filter(funded_category='ACTIVE')

    context = {
        'nav':'client_records_dcc', 
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'DCC Loans with Arrears'
        }

    return render(request, 'filtered_loan_list.html', context)

@admin_check
def filtered_loan_records_your_defaults(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    loans = Loan.objects.filter(lender=user_profile, category='FUNDED', status='DEFAULTED')
    
    context = {
        'nav':'client_records', 
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'Loans in Default'
        }

    return render(request, 'filtered_loan_list.html', context)

#loan records
@admin_check
def filtered_loan_records_dcc_defaults(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    loans = Loan.objects.filter(category='FUNDED', status='DEFAULTED')

    context = {
        'nav':'client_records_dcc', 
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'DCC Loans in Default'
        }

    return render(request, 'filtered_loan_list.html', context)

@admin_check
def filtered_loan_records_your_recovery(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    loans = Loan.objects.filter(lender=user_profile, funded_category='RECOVERY')
    context = {
        'nav':'client_records', 
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'Loans in Recovery'
        }

    return render(request, 'filtered_loan_list.html', context)

#loan records
@admin_check
def filtered_loan_records_dcc_recovery(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    loans = Loan.objects.filter(funded_category='RECOVERY')

    context = {
        'nav':'client_records_dcc', 
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'DCC Loans in Recovery'
        }

    return render(request, 'filtered_loan_list.html', context)