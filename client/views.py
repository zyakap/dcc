from django.conf import settings
from django.shortcuts import render, get_object_or_404
from datetime import datetime
from django.utils import timezone

import requests
from .models import ClientProfile, BusinessProfile, ClientContact, ClientAddress, ClientEmployer, ClientBankAccount, ClientUpload, ClientCreditScore
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

@login_check
def client_record_detail(request, client_id):
    """One client's record, pay-per-view gated exactly like the tenant LMS
    channel:

    - a tenant viewing ITS OWN client (same LUID) sees the data it supplied
      for free, with the cross-lender DCC section behind the unlock;
    - viewing anyone else's client shows only a teaser (name + record exists)
      behind the View Data overlay until a paid access window is open;
    - a paid window unlocks everything: full profile, all lenders' loans,
      the benchmark score and matched profiles."""
    from django.utils import timezone
    from django.db.models import Q, Sum
    from api.models import CreditCheckAccess, PricingSettings
    from loan.models import Loan
    from .models import matched_profiles

    client = get_object_or_404(ClientProfile, id=client_id)
    try:
        tenant = request.user.userprofile
    except Exception:
        tenant = None

    own_record = bool(tenant and client.LUID and client.LUID == tenant.LUID)
    dcc_enabled = bool(tenant and tenant.credit_check_enabled)

    # Free only when the client has no cross-lender data. The moment any
    # matched profile comes from a different lender the full record is billable.
    if own_record and client.CUID:
        all_profiles = matched_profiles(ClientProfile.objects.filter(pk=client.pk))
        has_external = any(p.LUID != tenant.LUID for p in all_profiles)
        if has_external:
            own_record = False  # treat as paid view — cross-lender data exists

    access = None
    if tenant and client.CUID:
        access = CreditCheckAccess.objects.filter(
            tenant=tenant,
            client_cuid=client.CUID,
            expires_at__gt=timezone.now(),
        ).order_by('-expires_at').first()
    dcc_access_valid = access is not None
    # Someone else's client (or own client with cross-lender data) + no paid window = teaser page only
    locked_page = not own_record and not dcc_access_valid

    pricing = PricingSettings.current()

    loans = Loan.objects.none()
    dcc_data = None
    credit_score = None

    if not locked_page:
        loan_q = Q(owner=client)
        if client.CUID:
            loan_q |= Q(UID=client.CUID, LUID=client.LUID)
        loans = Loan.objects.filter(loan_q).distinct().select_related('lender')

    if dcc_access_valid:
        profiles = matched_profiles(ClientProfile.objects.filter(pk=client.pk))
        other_profiles = [p for p in profiles if p.pk != client.pk]
        all_q = Q(owner__in=profiles)
        for p in profiles:
            if p.CUID:
                all_q |= Q(UID=p.CUID, LUID=p.LUID)
        all_loans = (Loan.objects.filter(all_q).distinct()
                     .select_related('lender', 'owner__user_profile').order_by('-created_at'))
        loan_summary = all_loans.aggregate(
            total_borrowed=Sum('amount'),
            total_outstanding=Sum('total_outstanding'),
            total_arrears=Sum('total_arrears'),
        )
        credit_score = ClientCreditScore.ensure(client, profiles=profiles)
        dcc_data = {
            'other_profiles': other_profiles,
            'all_loans': all_loans,
            'loan_summary': loan_summary,
        }

    return render(request, 'client_record_detail.html', {
        'nav': 'client_record_detail',
        'client': client,
        'loans': loans,
        'own_record': own_record,
        'locked_page': locked_page,
        'dcc_enabled': dcc_enabled,
        'dcc_access_valid': dcc_access_valid,
        'dcc_expires_at': access.expires_at if access else None,
        'dcc_data': dcc_data,
        'credit_score': credit_score,
        'tenant': tenant,
        'price_per_view': pricing.price_per_credit_check,
        'currency': pricing.currency,
    })


def dcc_credit_check_access(request, client_id):
    """POST: the web-channel 'View Data' trigger — unlocks (and bills) this
    client's DCC credit data through the same open_access service the tenant
    API uses, so both channels monetise identically."""
    from api.models import open_access
    from .models import matched_profiles

    if request.method != 'POST':
        return redirect('client_record_detail', client_id=client_id)

    client = get_object_or_404(ClientProfile, pk=client_id)
    try:
        tenant = request.user.userprofile
    except Exception:
        messages.error(request, 'No tenant profile.', extra_tags='danger')
        return redirect('client_record_detail', client_id=client_id)

    if not tenant.credit_check_enabled:
        messages.warning(request, 'DCC is disabled for your account.', extra_tags='warning')
        return redirect('client_record_detail', client_id=client_id)

    if not client.CUID:
        messages.warning(request, 'Client has no CUID — DCC access cannot be logged.', extra_tags='warning')
        return redirect('client_record_detail', client_id=client_id)

    own_record = bool(client.LUID and client.LUID == tenant.LUID)
    if own_record:
        profiles = matched_profiles(ClientProfile.objects.filter(pk=client.pk))
        has_external = any(p.LUID != tenant.LUID for p in profiles)
        if not has_external:
            messages.info(request, 'This is your own client record with no cross-lender data — available at no charge.', extra_tags='info')
            return redirect('client_record_detail', client_id=client_id)

    access, created = open_access(tenant, client.CUID)
    if created:
        try:
            profiles = matched_profiles(ClientProfile.objects.filter(pk=client.pk))
            ClientCreditScore.ensure(client, profiles=profiles)
        except Exception:
            pass
        # Audit trail: log the enquiry
        try:
            from client.models import EnquiryLog
            EnquiryLog.objects.create(client=client, tenant=tenant, query_type='CREDIT_CHECK')
        except Exception:
            pass
        window_hours = tenant.credit_check_window_hours or 12
        messages.success(
            request,
            f'DCC Credit data unlocked for {window_hours}h (until {access.expires_at:%d %b %Y %H:%M}). Billed.',
            extra_tags='info',
        )
    else:
        messages.info(request, f'DCC access already active until {access.expires_at:%d %b %Y %H:%M}.', extra_tags='info')
    return redirect('client_record_detail', client_id=client_id)

def client_record_detail_sample(request):

    return render(request, 'client_record_detail.html', {'nav': 'client_record_detail_sample'})


@login_check
def loan_detail(request, ref):
    """Tenant-accessible loan detail. Allowed when:
    - the loan belongs to the tenant's own clients (same LUID), OR
    - the tenant has a live DCC access window for the borrower's CUID.
    """
    from django.utils import timezone
    from loan.models import Loan
    from api.models import CreditCheckAccess

    loan = get_object_or_404(Loan, ref=ref)
    try:
        tenant = request.user.userprofile
    except Exception:
        messages.error(request, 'No tenant profile.', extra_tags='danger')
        return redirect('dashboard')

    own_loan = bool(loan.LUID and loan.LUID == tenant.LUID)
    dcc_access = False
    if not own_loan and loan.UID:
        dcc_access = CreditCheckAccess.objects.filter(
            tenant=tenant,
            client_cuid=loan.UID,
            expires_at__gt=timezone.now(),
        ).exists()

    if not own_loan and not dcc_access:
        messages.error(request, 'You do not have access to this loan record.', extra_tags='danger')
        if loan.owner:
            return redirect('client_record_detail', client_id=loan.owner.id)
        return redirect('dashboard')

    transactions = loan.transaction_set.all().order_by('-date')
    return render(request, 'loan_detail.html', {
        'nav': 'client_records_dcc',
        'loan': loan,
        'transactions': transactions,
    })

@login_check
def business_record_detail(request, business_id):
    from loan.models import Loan
    business = get_object_or_404(BusinessProfile, id=business_id)
    loans = Loan.objects.filter(owner=business.business_owner).select_related('lender') if business.business_owner else Loan.objects.none()
    return render(request, 'business_record_detail.html', {'nav': 'business_record_detail', 'business': business, 'loans': loans})

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
        if request.POST.get('dcc_Status') and request.POST.get('dcc_Status') != 'SELECT STATUS':
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

def _tenant_profile(request):
    """Return the UserProfile for the logged-in tenant, or None."""
    try:
        return request.user.userprofile
    except Exception:
        return None


def client_records(request):
    # A tenant sees ALL of their own records (vetted or not).
    # vetted=True was hiding synced records that hadn't been manually approved,
    # and was also leaking other tenants' vetted records to everyone.
    up = _tenant_profile(request)
    clients = ClientProfile.objects.filter(user_profile=up) if up else ClientProfile.objects.none()
    return render(request, 'client_records.html', {'nav':'client_records', 'clients': clients})

def client_records_under_review(request):
    up = _tenant_profile(request)
    clients = ClientProfile.objects.filter(user_profile=up, vetted=False) if up else ClientProfile.objects.none()
    return render(request, 'client_records_under_review.html', {'nav':'client_records_under_review', 'clients': clients})

def client_records_dcc(request):
    from django.utils import timezone
    from api.models import CreditCheckAccess

    clients = ClientProfile.objects.filter(vetted=True)
    try:
        tenant = request.user.userprofile
    except Exception:
        tenant = None

    paid_cuids = set()
    tenant_luid = None
    if tenant:
        tenant_luid = tenant.LUID
        paid_cuids = set(
            CreditCheckAccess.objects.filter(
                tenant=tenant,
                expires_at__gt=timezone.now(),
            ).values_list('client_cuid', flat=True)
        )

    return render(request, 'client_records_dcc.html', {
        'nav': 'client_records_dcc',
        'clients': clients,
        'paid_cuids': paid_cuids,
        'tenant_luid': tenant_luid,
    })

def business_records(request):
    up = _tenant_profile(request)
    businesses = BusinessProfile.objects.filter(user_profile=up) if up else BusinessProfile.objects.none()
    return render(request, 'business_records.html', {'nav':'business_records', 'businesses': businesses})

def business_records_dcc(request):
    # Database view: all vetted business records across every tenant
    businesses = BusinessProfile.objects.filter(vetted=True)
    return render(request, 'business_records_dcc.html', {'nav':'business_records_dcc', 'businesses': businesses})

def recent_client_records_dcc(request):
    # Database view: recently updated vetted records across every tenant
    clients = ClientProfile.objects.filter(vetted=True)
    return render(request, 'recent_client_records.html', {'nav':'recent_client_records_dcc', 'clients': clients})

def recovery_insights(request):
    # Database view: all vetted records for recovery analysis
    clients = ClientProfile.objects.filter(vetted=True)
    return render(request, 'recovery_insights.html', {'nav':'recovery_insights', 'clients': clients})





@login_check
def filtered_client_records_your_records_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    clients = ClientProfile.objects.filter(user_profile=user_profile, created_at__date=_today)
    context = {
        'nav': 'client_records',
        'clients': clients,
        'count': clients.count(),
        'descriptor': f'Your records created today ({_today})',
    }
    return render(request, 'filtered_client_records.html', context)

@login_check
def filtered_client_records_your_updated_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    clients = ClientProfile.objects.filter(user_profile=user_profile, updated_at__date=_today)
    context = {
        'nav': 'client_records',
        'clients': clients,
        'count': clients.count(),
        'descriptor': f'Your records updated today ({_today})',
    }
    return render(request, 'filtered_client_records.html', context)

@login_check
def filtered_records_your_business_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    businesses = BusinessProfile.objects.filter(user_profile=user_profile, created_at__date=_today)
    context = {
        'nav': 'business_records',
        'businesses': businesses,
        'count': businesses.count(),
        'descriptor': f'Your business records added today ({_today})',
    }
    return render(request, 'filtered_business_records.html', context)

@login_check
def filtered_client_records_dcc_records_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    clients = ClientProfile.objects.filter(vetted=True, created_at__date=_today)
    context = {
        'nav': 'client_records_dcc',
        'clients': clients,
        'count': clients.count(),
        'descriptor': f'DCC Client Records created today ({_today})',
    }
    return render(request, 'filtered_client_records.html', context)

@login_check
def filtered_client_records_dcc_updated_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    clients = ClientProfile.objects.filter(vetted=True, updated_at__date=_today)
    context = {
        'nav': 'client_records_dcc',
        'clients': clients,
        'count': clients.count(),
        'descriptor': f'DCC Client Records updated today ({_today})',
    }
    return render(request, 'filtered_client_records.html', context)

@login_check
def filtered_business_records_dcc_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    businesses = BusinessProfile.objects.filter(vetted=True, created_at__date=_today)
    context = {
        'nav': 'business_records_dcc',
        'businesses': businesses,
        'count': businesses.count(),
        'descriptor': f'DCC Business Records added today ({_today})',
    }
    return render(request, 'filtered_business_records.html', context)

@login_check
def filtered_business_records_dcc_updated_today(request):
    from django.utils import timezone
    _today = timezone.localdate()
    businesses = BusinessProfile.objects.filter(vetted=True, updated_at__date=_today)
    context = {
        'nav': 'business_records_dcc',
        'businesses': businesses,
        'count': businesses.count(),
        'descriptor': f'DCC Business Records updated today ({_today})',
    }
    return render(request, 'filtered_business_records.html', context)

from loan.models import Loan
from django.http import Http404

@login_check
def filtered_loan_records_your_arrears(request):
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    loans = Loan.objects.filter(lender=user_profile, funded_category='ACTIVE', total_arrears__gt=0)
    context = {
        'nav': 'client_records',
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'Your Loans with Arrears',
    }
    return render(request, 'filtered_loan_list.html', context)

@login_check
def filtered_loan_records_dcc_arrears(request):
    loans = Loan.objects.filter(funded_category='ACTIVE', total_arrears__gt=0)
    context = {
        'nav': 'client_records_dcc',
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'DCC Loans with Arrears',
    }
    return render(request, 'filtered_loan_list.html', context)

@login_check
def filtered_loan_records_your_defaults(request):
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    loans = Loan.objects.filter(lender=user_profile, status='DEFAULTED')
    context = {
        'nav': 'client_records',
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'Your Loans in Default',
    }
    return render(request, 'filtered_loan_list.html', context)

@login_check
def filtered_loan_records_dcc_defaults(request):
    loans = Loan.objects.filter(status='DEFAULTED')
    context = {
        'nav': 'client_records_dcc',
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'DCC Loans in Default',
    }
    return render(request, 'filtered_loan_list.html', context)

@login_check
def filtered_loan_records_your_recovery(request):
    user_profile = UserProfile.objects.get(user_id=request.user.id)
    loans = Loan.objects.filter(lender=user_profile, funded_category='RECOVERY')
    context = {
        'nav': 'client_records',
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'Your Loans in Recovery',
    }
    return render(request, 'filtered_loan_list.html', context)

@login_check
def filtered_loan_records_dcc_recovery(request):
    loans = Loan.objects.filter(funded_category='RECOVERY')
    context = {
        'nav': 'client_records_dcc',
        'loans': loans,
        'count': loans.count(),
        'descriptor': 'DCC Loans in Recovery',
    }
    return render(request, 'filtered_loan_list.html', context)

# ============================================================================
# Default Notice workflow
# ============================================================================

@login_check
def submit_default_notice(request, client_id):
    from client.models import DefaultNotice
    user_profile = UserProfile.objects.get(user=request.user)
    client = get_object_or_404(ClientProfile, pk=client_id)

    if request.method == 'POST':
        amount = request.POST.get('amount_owed', '').strip()
        reason = request.POST.get('reason', '').strip()
        loan_ref = request.POST.get('loan_ref', '').strip()
        grace   = int(request.POST.get('grace_days', 14))

        if not amount or not reason:
            messages.error(request, 'Amount and reason are required.', extra_tags='danger')
        else:
            from decimal import Decimal, InvalidOperation
            try:
                amount_dec = Decimal(amount)
            except InvalidOperation:
                messages.error(request, 'Invalid amount.', extra_tags='danger')
                amount_dec = None
            if amount_dec:
                notice = DefaultNotice.objects.create(
                    client=client,
                    tenant=user_profile,
                    loan_ref=loan_ref,
                    amount_owed=amount_dec,
                    reason=reason,
                    grace_days=grace,
                    status='SUBMITTED',
                    submitted_at=timezone.now(),
                )
                _send_credit_alert(
                    client, user_profile,
                    f'Default notice submitted for {client.first_name} {client.last_name} '
                    f'(CUID {client.CUID}) — K {amount_dec:.2f}.',
                )
                messages.success(request, 'Default notice submitted. DCC will review and notify the borrower.', extra_tags='success')
                return redirect('client_record_detail', client_id=client.id)

    return render(request, 'client/submit_default_notice.html', {
        'client': client,
        'nav':    'client_records',
    })


@login_check
def my_default_notices(request):
    from client.models import DefaultNotice
    user_profile = UserProfile.objects.get(user=request.user)
    notices = DefaultNotice.objects.filter(tenant=user_profile).select_related('client')
    return render(request, 'client/my_default_notices.html', {
        'notices': notices,
        'nav':     'client_records',
    })


# ============================================================================
# Dispute workflow  (tenant-side submission)
# ============================================================================

@login_check
def submit_dispute(request, client_id):
    from client.models import Dispute
    user_profile = UserProfile.objects.get(user=request.user)
    client = get_object_or_404(ClientProfile, pk=client_id)

    if request.method == 'POST':
        dtype = request.POST.get('dispute_type', 'OTHER')
        field = request.POST.get('field_disputed', '').strip()
        desc  = request.POST.get('description', '').strip()
        doc   = request.FILES.get('supporting_doc')

        if not desc:
            messages.error(request, 'Please describe the issue.', extra_tags='danger')
        else:
            Dispute.objects.create(
                client=client,
                filed_by_tenant=user_profile,
                dispute_type=dtype,
                field_disputed=field,
                description=desc,
                supporting_doc=doc,
            )
            messages.success(request, 'Dispute submitted. DCC will review within 5 business days.', extra_tags='success')
            return redirect('client_record_detail', client_id=client.id)

    return render(request, 'client/submit_dispute.html', {
        'client':       client,
        'type_choices': Dispute.TYPE_CHOICES,
        'nav':          'client_records',
    })


# ============================================================================
# Consent management
# ============================================================================

@login_check
def record_consent(request, client_id):
    from client.models import ClientConsent
    user_profile = UserProfile.objects.get(user=request.user)
    client = get_object_or_404(ClientProfile, pk=client_id)

    if request.method == 'POST':
        ctype  = request.POST.get('consent_type', 'CREDIT_CHECK')
        method = request.POST.get('method', 'PAPER')
        ref    = request.POST.get('reference', '').strip()
        notes  = request.POST.get('notes', '').strip()
        doc    = request.FILES.get('document')
        from django.utils.dateparse import parse_datetime, parse_date
        expires_raw = request.POST.get('expires_at', '').strip()
        expires = None
        if expires_raw:
            from datetime import datetime
            try:
                expires = timezone.make_aware(datetime.strptime(expires_raw, '%Y-%m-%d'))
            except ValueError:
                pass

        ClientConsent.objects.create(
            client=client,
            tenant=user_profile,
            consent_type=ctype,
            method=method,
            reference=ref,
            notes=notes,
            document=doc,
            expires_at=expires,
        )
        messages.success(request, 'Consent recorded.', extra_tags='success')
        return redirect('client_record_detail', client_id=client.id)

    return render(request, 'client/record_consent.html', {
        'client':        client,
        'consent_types': ClientConsent.CONSENT_TYPES,
        'methods':       ClientConsent.METHODS,
        'nav':           'client_records',
    })


@login_check
def client_consents(request, client_id):
    from client.models import ClientConsent
    user_profile = UserProfile.objects.get(user=request.user)
    client = get_object_or_404(ClientProfile, pk=client_id)
    consents = ClientConsent.objects.filter(client=client, tenant=user_profile)
    return render(request, 'client/client_consents.html', {
        'client':   client,
        'consents': consents,
        'nav':      'client_records',
    })


# ============================================================================
# Credit Report PDF
# ============================================================================

@login_check
def credit_report_pdf(request, client_id):
    from wkhtmltopdf.views import PDFTemplateResponse
    from client.models import matched_profiles
    from loan.models import Loan

    user_profile = UserProfile.objects.get(user=request.user)
    client = get_object_or_404(ClientProfile, pk=client_id)
    all_profiles = matched_profiles(ClientProfile.objects.filter(pk=client_id))
    primary = sorted(all_profiles, key=lambda p: p.updated_at or p.created_at, reverse=True)[0]
    score  = getattr(primary, 'credit_score', None)
    loans  = Loan.objects.filter(owner__in=all_profiles).order_by('-funding_date')

    # Log enquiry
    from client.models import EnquiryLog
    EnquiryLog.objects.create(client=primary, tenant=user_profile, query_type='CREDIT_CHECK')

    context = {
        'client':   primary,
        'score':    score,
        'loans':    loans,
        'tenant':   user_profile,
        'generated_at': timezone.now(),
    }
    filename = f'DCC_CreditReport_{primary.CUID or primary.pk}.pdf'
    return PDFTemplateResponse(request, 'client/credit_report_pdf.html', context=context, filename=filename)


# ============================================================================
# Portfolio analytics helpers
# ============================================================================

@login_check
def portfolio_analytics(request):
    from django.db.models import Sum, Count, Q
    from loan.models import Loan

    user_profile = UserProfile.objects.get(user=request.user)
    loans = Loan.objects.filter(lender=user_profile)

    aging = {
        '0_30':   loans.filter(days_in_default__gt=0, days_in_default__lte=30).aggregate(n=Count('id'), amt=Sum('total_arrears')),
        '31_60':  loans.filter(days_in_default__gt=30, days_in_default__lte=60).aggregate(n=Count('id'), amt=Sum('total_arrears')),
        '61_90':  loans.filter(days_in_default__gt=60, days_in_default__lte=90).aggregate(n=Count('id'), amt=Sum('total_arrears')),
        '91_120': loans.filter(days_in_default__gt=90, days_in_default__lte=120).aggregate(n=Count('id'), amt=Sum('total_arrears')),
        '120p':   loans.filter(days_in_default__gt=120).aggregate(n=Count('id'), amt=Sum('total_arrears')),
    }

    agg = loans.aggregate(
        total_portfolio=Sum('amount'),
        total_outstanding=Sum('total_outstanding'),
        total_arrears=Sum('total_arrears'),
    )

    running   = loans.filter(status='RUNNING').count()
    defaulted = loans.filter(status='DEFAULTED').count()
    recovery  = loans.filter(funded_category='RECOVERY').count()
    completed = loans.filter(status='COMPLETED').count()

    top_arrears = loans.filter(total_arrears__gt=0).order_by('-total_arrears')[:10]

    return render(request, 'users/portfolio_analytics.html', {
        'nav':             'dashboard',
        'user':            user_profile,
        'aging':           aging,
        'agg':             agg,
        'running':         running,
        'defaulted':       defaulted,
        'recovery':        recovery,
        'completed':       completed,
        'top_arrears':     top_arrears,
    })


# ============================================================================
# Shared alert helper
# ============================================================================

def _send_credit_alert(client, triggering_tenant, message_body):
    """Email the originating tenant(s) when a credit event occurs on their borrower."""
    from api.models import PlatformSettings
    settings_obj = PlatformSettings.current()
    if not settings_obj.alert_on_status_change:
        return
    try:
        from django.conf import settings as dj_settings
        from django.core.mail import send_mail
        owners = list(ClientProfile.objects.filter(CUID=client.CUID).values_list('user_profile__work_email', flat=True).distinct())
        recipients = [e for e in owners if e]
        if not recipients:
            return
        send_mail(
            subject=f'DCC Credit Alert — {client.first_name} {client.last_name}',
            message=message_body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=True,
        )
    except Exception:
        pass
