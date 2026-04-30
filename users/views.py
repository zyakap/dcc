import datetime
from cgi import FieldStorage
from decimal import Decimal
# from distutils.command.upload import upload
from socket import gaierror
from django.conf import settings
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import (
    SetPasswordForm,
)
from django.contrib.auth import get_user_model
from django.db import ProgrammingError
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse
from .forms import (
    ContactInfoForm, RegisterForm, LoginForm, ContactInfoForm, 
    OrganisationInfoUpdateForm, PasswordResetForm,  BusinessUploadForm,
    )
from django.db.models import Sum
from .models import UserProfile
from django.contrib import messages
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode
from .tokens import account_activation_token

#EMAIL SETTINGS
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.html import strip_tags
#admin sender email
sender = settings.DEFAULT_FROM_EMAIL

from django.conf import settings
from django.db.models import Q

#FILES UPLOAD
from django.core.files.storage import FileSystemStorage

#functions
from .functions import id_generator, send_email, login_check, admin_check, fileuploader, check_staff
#from message.models import Message, MessageLog
#from support.models import SupportTicket, SupportTicketThread

User = get_user_model() 
user = User()
domain = settings.DOMAIN

from django.http import JsonResponse
from admin1.models import Subscriber, DefaultListSubmission

##### DCCC
from django.shortcuts import render
from django.db.models import Q
from client.models import ClientProfile, BusinessProfile
from django.shortcuts import render, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required

from django.views.decorators.csrf import csrf_exempt

from client.models import ClientProfile, BusinessProfile, ClientUpload, ClientAddress, ClientContact, ClientEmployer, ClientBankAccount, Payslip

#views start here

##### ACCOUNT CONTROL #####

@admin_check
def suspend_user(request, uid):
    
    user = User.objects.get(pk=uid)
    user.suspended = True
    user.save()

    
    
    subject = 'LOAN ACCOUNT DEACTIVATED'
    ''' if header_cta == 'yes' '''
    cta_link = 'http://www.webmasta.com.pg'
    cta_label = 'Request Activation'

    greeting = f'Hello {user.email}'
    message = 'You loan account was deactivated due to a lot of defaults.'
    message_details = 'This will have a negative impact on your credit rating \
        which is used by a lot of local organisation to decide on loan products. \
            You should fix this with us to maintain good credit rating.'

    ''' if cta == 'yes' '''
    cta_btn1_link = 'http://dcc.com.pg'
    cta_btn1_label = 'REQUEST ACTIVATION'
    cta_btn2_link = 'http://dcc.com.pg/cancel/'
    cta_btn2_label = 'Cancel'

    ''' if promo == 'yes' '''
    catchphrase = 'TIP:'
    promo_title = 'CREDIT RATING AFFECTS EVERYTHING'
    promo_message = 'A Low credit rating will prevent borrowing and good business opportunities.'
    promo_cta_link = 'http://dcc.com.pg/fix/'
    promo_cta = 'Fix Credit Rating'
    
    email_content = render_to_string('custom/email_temp_general.html', {
        'header_cta': 'yes',
        'cta': 'yes',
        'cta_btn2': 'yes',
        'promo': 'yes',
        'cta_link': cta_link,
        'cta_label': cta_label,
        'subject': subject,
        'greeting': greeting,
        'message': message,
        'message_details': message_details,
        'cta_btn1_link': cta_btn1_link,
        'cta_btn1_label': cta_btn1_label,
        'cta_btn2_link': cta_btn2_link,
        'cta_btn2_label': cta_btn2_label,
        'catchphrase': catchphrase,
        'promo_title': promo_title,
        'promo_message': promo_message,
        'promo_cta_link': promo_cta_link,
        'promo_cta': promo_cta,
        'user': user,
        'domain': domain,
        
    })
    text_content = strip_tags(email_content)
    email = EmailMultiAlternatives(subject,text_content,sender,['dev@webmasta.com.pg', user.email ])
    email.attach_alternative(email_content, "text/html")

    try: 
        email.send()
        messages.success(request, "Success Message")
    except:
        messages.error(request, 'Error Message', extra_tags='danger')
        
    return redirect('view_customer', uid)

@admin_check
def activate_user(request, uid):

    user = UserProfile.objects.get(pk=uid)
    user.activation = 1
    user.save()

    #create user's activity log
  
    try:
        MessageLog.objects.create(user=user)
    except:
        pass

    
    subject = 'LOAN ACCOUNT ACTIVATED'
    greeting = 'Hello'
    message = 'Your loan account has been activated.'
    details = 'Now you can start applying for loans. Remember, more information on your profile will help us make loan decisons faster so please do upload as much information as you can.'
    btn_label = 'APPLY'
    btn_link = f'{domain}/loan/apply/'

    email_content = render_to_string('custom/email_temp_general.html', {
        'subject': subject,
        'greeting': greeting,
        'message': message,
        'message_details': details,
        'action_btn_1': btn_label,
        'action_btn_1_link' : btn_link,
        'user': user,
        'domain': domain,  
    })

    text_content = strip_tags(email_content)
    email = EmailMultiAlternatives(subject,text_content,sender,['dev@webmasta.com.pg', user.email ])
    email.attach_alternative(email_content, "text/html")

    try: 
        email.send()
        messages.success(request, "User Loan Account was activated and Email was sent to notify user.")
    except:
        messages.error(request, 'User account is activated BUT user email notification was not sent.', extra_tags='danger')
        
    return redirect('view_customer', uid)

@admin_check
def deactivate_user(request, uid):

    user = UserProfile.objects.get(pk=uid)
    user.activation = 0
    user.save()

    #create user's activity log
  
    
    subject = 'LOAN ACCOUNT DE-ACTIVATED'
    greeting = 'Hello'
    message = 'Your loan account has been deactivated.'
    details = 'Now you can NOT apply for loans.'
    btn_label = 'REACTIVATE'
    btn_link = f'#'

    email_content = render_to_string('custom/email_temp_general.html', {
        'subject': subject,
        'greeting': greeting,
        'message': message,
        'message_details': details,
        'action_btn_1': btn_label,
        'action_btn_1_link' : btn_link,
        'user': user,
        'domain': domain,  
    })

    text_content = strip_tags(email_content)
    email = EmailMultiAlternatives(subject,text_content,sender,['dev@webmasta.com.pg', user.email ])
    email.attach_alternative(email_content, "text/html")

    try: 
        email.send()
        messages.success(request, "User Loan Account was Deactivated and Email was sent to notify user.")
    except:
        messages.error(request, 'User account is deactivated BUT user email notification was not sent.', extra_tags='danger')
        
    return redirect('view_customer', uid)

##############
##  AUTHENTICATION 
##############

def activation_sent(request):
    return render(request, 'activation_sent.html')

def activation_invalid(request):
    return render(request, 'activation_invalid.html')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user,token):
        user.is_active = True
        user.confirmed = True
        user.save()
        
         # Manually specify the backend
        user.backend = 'users.backends.EmailOrUsernameModelBackend'  # Replace with your actual backend path
        login(request, user)
        #print(user)
        #messages.success(request, 'Make sure to switch to admin and click on instructions to learn on basics of how to use the app.', extra_tags="info")
        return redirect('profile')
    else:
        if user is None:
            messages.error(request, 'You are not registered, please register', extra_tags='dark')
            return render(request, 'activation_invalid.html')
        else:
            messages.error(request, 'You are already registered, please login', extra_tags='dark')
            return redirect('login_user')      
        
def password_reset(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user,token):
        
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)  # Important!
                messages.success(request, 'Your password was successfully reset!')
                return redirect('login_user')
            else:
                messages.error(request, 'Please correct the error below.', extra_tags='danger')
        else:
            form = SetPasswordForm(user)
            
        return render(request, 'reset_password_form.html', {'form': form})
    else:
        return render(request, 'activation_invalid.html')
      
def register(request):
    if request.method == 'POST':

        organisation = request.POST.get('organisation')
        name = request.POST.get('name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        if request.POST.get('terms') == 'on':
            terms = True
        else:
            messages.error(request, "You must agree to the terms and conditions to register.", extra_tags='danger')
            return redirect('register')

        emailexists = User.objects.filter(email=email)
        if len(emailexists) != 0:
            messages.error(request, "There is an account already registered with this email address.", extra_tags='danger')
            return render(request, 'bm_login.html')
        
        userexists = User.objects.filter(username=username)
        if len(userexists) != 0:
            messages.error(request, "There is an account already registered with this username.", extra_tags='danger')
            return render(request, 'bm_login.html')


        # Now use create_user method to create a new user
        user = User.objects.create_user(email=email, username=username, password=password)
        # Set other attributes if needed, e.g., user.name = name

        # Save the user
        user.save()

        # inactivate the user
        user.is_active=False
        user.save()

        name = request.POST.get('name')
        name_split = list(name.split())

        first_name = name_split[0]
        if len(name_split) > 2:
            middle_name = ' '.join(name_split[1:-1])
        else:
            middle_name = None
        
        last_name = name_split[-1]

        userprofile = UserProfile.objects.create(user_id=user.id, first_name=first_name, middle_name=middle_name, last_name=last_name, organisation=organisation)
        userprofile.save()

        #to send email
        # HTML EMAIL
            
        email_subject = 'Activate your Account'
        token_message = render_to_string('activation_request.html', {
            'user': user,
            'domain': domain,
            'cta': 'yes',
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        })
        text_content = strip_tags(token_message)
        email = EmailMultiAlternatives(
            email_subject,
            text_content,
            'Dinau Control <admin@dc.com.pg>',
            [user.email ],
            bcc=['dev@webmasta.com.pg']
        )
        email.attach_alternative(token_message, "text/html")

        try:
            email.send()
            return redirect('activation_sent')
        except:
            messages.error(request, "The activation token email could not be sent, make sure you have internet connection and try again.", extra_tags='danger')
            uid = user.id
            UserProfile.objects.get(user=user).delete()
            User.objects.get(pk=uid).delete()

    return render(request, 'bm_register.html')

def reset_password(request):
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            
            email = form.cleaned_data['email']
            user = User.objects.get(email = email)
            #print(user)
            #messages.error(request, 'User does not exist!', extra_tags="danger")
            #return redirect('dashboard')
            if not user:
                messages.error(request, 'User does not exist!', extra_tags="danger")
                return redirect('reset_password')
            current_user = User.objects.get(email=email)
            
            if current_user.active == False:
                messages.error(request, 'Inactive users are not allowed to reset their password. Contact us at users@ibx.com', extra_tags="danger")
                return redirect('reset_password')
            
            #to send email
            current_site = settings.DOMAIN
            subject='Reset your account\'s Password'
            token_message = render_to_string('password_reset.html', {
                'user': current_user,
                'cta': 'yes',
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(current_user.pk)),
                'token': account_activation_token.make_token(current_user),
            })
            text_content = strip_tags(token_message)
            email = EmailMultiAlternatives(
                subject,
                text_content,
                settings.EMAIL_HOST_USER,
                ['dev@webmasta.com.pg', user.email ]
            )
            email.attach_alternative(token_message, "text/html")
            try:
                email.send()
                return redirect('reset_link_sent')
            except:
                messages.error(request, "The reset token email could not be sent, make sure you have internet connection and try again.", extra_tags='danger')
                return redirect('reset_password')
    else: 
        form = PasswordResetForm()
    return render(request, 'reset_password.html', {'form': form})            
            
def login_user(request):
    
    if request.user.is_authenticated:
        return redirect( 'dashboard' )
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        print(username)
        print(password)

        user = authenticate(request, email=username, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, 'Welcome to your dashboard...')
            if user.id == 1:
                messages.success(request, 'Make sure to switch to admin and click on instructions to learn on basics of how to use the app.', extra_tags="info")
            try:
                user_profile = UserProfile.objects.get(user_id=user.id)
            except:
                messages.error(request, "You did not activate your profile yet using the activation link sent to your email.", extra_tags="warning")
                messages.error(request, "We are deleting this account, please register again.", extra_tags="info")
                user.delete()
                return redirect('register')
            user_profile.login_timestamp = datetime.datetime.now()
            user_profile.save()
            
            return redirect('dashboard')
        else:
            messages.error(request, 'User does not exist.', extra_tags='danger')
            return redirect('login_user')

    return render(request, 'bm_login.html')

def logout_user(request):
    logout(request)
    messages.success(request, 'You have logged out...')
    return redirect('login_user')

def reset_link_sent(request):
    return render(request, 'reset_link_sent.html')

##############
##  PROFILE MANAGEMENT
##############

@login_check
def dashboard(request):
    
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    if request.method == 'POST':
        search_string = request.POST.get('search_string')
        return redirect('database_search_redirect', search_string )

    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)
    
    dcc_records_today = ClientProfile.objects.filter(created_at__lt=today)
    dcc_records_yesterday = ClientProfile.objects.filter(created_at__gt=yesterday)
    dcc_records_today_count = dcc_records_today.count()
    dcc_records_yesterday_count = dcc_records_yesterday.count()
    dcc_updated_today = ClientProfile.objects.filter(updated_at__gt=today)
    dcc_updated_yesterday = ClientProfile.objects.filter(updated_at__gt=yesterday)
    dcc_updated_today_count = dcc_updated_today.count()
    dcc_updated_yesterday_count = dcc_updated_yesterday.count()
    dcc_business_today = BusinessProfile.objects.filter(updated_at__lt=today)
    dcc_business_yesterday = BusinessProfile.objects.filter(updated_at__gt=yesterday)
    dcc_business_today_count = dcc_business_today.count()
    dcc_business_yesterday_count = dcc_business_yesterday.count()

    your_records_today = ClientProfile.objects.filter(user_profile=user_profile, created_at__lt=today)
    your_records_yesterday = ClientProfile.objects.filter(user_profile=user_profile, created_at__gt=yesterday)
    your_records_today_count = your_records_today.count()
    your_records_yesterday_count = your_records_yesterday.count()
    your_updated_today = ClientProfile.objects.filter(user_profile=user_profile, updated_at__gt=today)
    your_updated_yesterday = ClientProfile.objects.filter(user_profile=user_profile, updated_at__gt=yesterday)
    your_updated_today_count = your_updated_today.count()
    your_updated_yesterday_count = your_updated_yesterday.count()
    your_business_today = BusinessProfile.objects.filter(user_profile=user_profile, updated_at__lt=today)
    your_business_yesterday = BusinessProfile.objects.filter(user_profile=user_profile, updated_at__gt=yesterday)
    your_business_today_count = your_business_today.count()
    your_business_yesterday_count = your_business_yesterday.count()

    if (dcc_records_today_count + dcc_records_yesterday_count) != 0:
        dcc_records_percentage_change = (dcc_records_today_count / (dcc_records_today_count + dcc_records_yesterday_count)) * 100
    else:
        dcc_records_percentage_change = 0

    if (dcc_updated_today_count + dcc_updated_yesterday_count) != 0:
        dcc_updated_percentage_change = (dcc_updated_today_count / (dcc_updated_today_count + dcc_updated_yesterday_count)) * 100
    else:
        dcc_updated_percentage_change = 0

    if (dcc_business_today_count + dcc_business_yesterday_count) != 0:
        dcc_business_percentage_change = (dcc_business_today_count / (dcc_business_today_count + dcc_business_yesterday_count)) * 100
    else:
        dcc_business_percentage_change = 0

    if (your_records_today_count + your_records_yesterday_count) != 0:
        your_records_percentage_change = (your_records_today_count / (your_records_today_count + your_records_yesterday_count)) * 100
    else:
        your_records_percentage_change = 0

    if (your_updated_today_count + your_updated_yesterday_count) != 0:
        your_updated_percentage_change = (your_updated_today_count / (your_updated_today_count + your_updated_yesterday_count)) * 100
    else:
        your_updated_percentage_change = 0

    if (your_business_today_count + your_business_yesterday_count) != 0:
        your_business_percentage_change = (your_business_today_count / (your_business_today_count + your_business_yesterday_count)) * 100
    else:
        your_business_percentage_change = 0
    
    print(type(dcc_records_today))
    print(dcc_records_today)

    from loan.models import Loan

    your_arrears = Loan.objects.filter(lender=user_profile, funded_category='ACTIVE')
    your_arrears_count = your_arrears.count()
    your_total_arrears = your_arrears.aggregate(total=Sum('total_arrears'))['total'] or 0
    your_defaults = Loan.objects.filter(lender=user_profile, category='FUNDED', status='DEFAULTED')
    your_defaults_count = your_defaults.count()
    your_total_defaults = your_defaults.aggregate(total=Sum('total_outstanding'))['total'] or 0
    your_recovery = Loan.objects.filter(lender=user_profile, funded_category='RECOVERY')
    your_recovery_count = your_recovery.count()
    your_total_recovery = your_recovery.aggregate(total=Sum('total_outstanding'))['total'] or 0

    dcc_arrears = Loan.objects.filter(funded_category='ACTIVE')
    dcc_arrears_count = dcc_arrears.count()
    dcc_total_arrears = dcc_arrears.aggregate(total=Sum('total_arrears'))['total'] or 0
    dcc_defaults = Loan.objects.filter(category='FUNDED', status='DEFAULTED')
    dcc_defaults_count = dcc_defaults.count()
    dcc_total_defaults = dcc_defaults.aggregate(total=Sum('total_outstanding'))['total'] or 0
    dcc_recovery = Loan.objects.filter(funded_category='RECOVERY')
    dcc_recovery_count = dcc_recovery.count()
    dcc_total_recovery = dcc_recovery.aggregate(total=Sum('total_outstanding'))['total'] or 0


    context = {
        'domain':domain,
        'nav':'dashboard',
        'user': user_profile,
        'dcc_records_today':dcc_records_today,
        'dcc_records_today_count':dcc_records_today_count,
        'dcc_updated_today':dcc_updated_today,
        'dcc_updated_today_count':dcc_updated_today_count,
        'dcc_business_today':dcc_business_today,
        'dcc_business_today_count':dcc_business_today_count,
        'your_records_today':your_records_today,
        'your_records_today_count':your_records_today_count,
        'your_updated_today':your_updated_today,
        'your_updated_today_count':your_updated_today_count,
        'your_business_today':your_business_today,
        'your_business_today_count':your_business_today_count,
        'dcc_records_percentage_change':dcc_records_percentage_change,
        'dcc_updated_percentage_change':dcc_updated_percentage_change,
        'dcc_business_percentage_change':dcc_business_percentage_change,
        'your_records_percentage_change':your_records_percentage_change,
        'your_updated_percentage_change':your_updated_percentage_change,
        'your_business_percentage_change':your_business_percentage_change,

        'your_total_arrears':your_total_arrears,
        'your_total_defaults':your_total_defaults,
        'your_total_recovery':your_total_recovery,
        
        'dcc_total_arrears':dcc_total_arrears,
        'dcc_total_defaults':dcc_total_defaults,
        'dcc_total_recovery':dcc_total_recovery,
        
        'dcc_arrears_count':dcc_arrears_count,
        'dcc_defaults_count':dcc_defaults_count,
        'dcc_recovery_count':dcc_recovery_count,
        
        'your_arrears_count':your_arrears_count,
        'your_defaults_count':your_defaults_count,
        'your_recovery_count':your_recovery_count,

    }
    return render(request, 'dashboard.html', context)


@login_check
def profile(request):
    
    if request.user.is_authenticated:
        current_user = request.user
        uid = current_user.id
        try:
            user = UserProfile.objects.get(user_id=uid)
            print(user)
        except:
            messages.error(request,'Profile for this user does not exist.Register new account or Contact ibx@instabuxx.com', extra_tags='danger')
            return redirect('register')
        if user is None:
            return redirect('edit_profile')
        return render(request, 'profile.html', { 'nav':'profile','current_user': current_user, 'user': user })
    return redirect('login_user')

@login_check
def edit_contact_info(request):
    if request.user.is_authenticated:
        ca_user = request.user.id
        user_profile = UserProfile.objects.get(user_id=ca_user)
        uid = user_profile.id
        user = UserProfile.objects.get(pk=uid)
        
        initial_data = {
            'first_name': user.first_name,
            'middle_name': user.middle_name,
            'last_name': user.last_name,
            'role': user.role,
            'email': user.email,
            'mobile1': user.mobile1,
        }
       
        if request.method == 'POST':
            contactInfoUpdateForm = ContactInfoForm(request.POST)
            if  contactInfoUpdateForm.is_valid():
                
                user.first_name = contactInfoUpdateForm.cleaned_data['first_name']
                user.middle_name = contactInfoUpdateForm.cleaned_data['middle_name']
                user.last_name = contactInfoUpdateForm.cleaned_data['last_name']
                user.role = contactInfoUpdateForm.cleaned_data['role']
                user.email = contactInfoUpdateForm.cleaned_data['email']
                user.mobile1 = contactInfoUpdateForm.cleaned_data['mobile1']
                user.save()

                if user.first_name and user.last_name:
                    first_name_initial = user.first_name[0]
                    last_name_initial = user.last_name[0]
                    randnum = id_generator(6)
                    fint = f'{first_name_initial}{last_name_initial}{randnum}'
                    if not user.uid:
                        user.uid = f'{fint}'
                    #user.uid = fint
                        user.save()

                messages.success(request, 'Contact information updated successfully!')
            return redirect('profile')
        else:
            contactInfoUpdateForm = ContactInfoForm(initial=initial_data)
        return render(request, 'edit_contact_info.html', {'nav':'profile','form':contactInfoUpdateForm, 'cau': ca_user })
    return redirect('login_user')

@login_check
def edit_uploads(request):
    if request.user.is_authenticated:
        uid = request.user.id
        user = UserProfile.objects.get(user_id=uid)
        
        
        if request.method == 'POST':
            uploadform = BusinessUploadForm(request.POST)
            
            if user.first_name == '' and user.last_name == '':
                messages.error(request, 'You need to update your First Name and Last Name first...')
                return redirect('edit_contact_info')
            
            if uploadform.is_valid():
                
                if 'ipa' in request.FILES:
                    fileuploader(request, 'ipa', user)
                    
                if 'tin' in request.FILES:
                    fileuploader(request, 'tin', user)
                   
                messages.success(request, 'Certificates uploaded Successfully!') 
                return redirect('profile')
        else:
            uploadform = BusinessUploadForm()        
        return render(request, 'edit_uploads.html', { 'nav': 'profile', 'form': uploadform, })   
                
    return redirect('login_user')

@login_check
def edit_organisation_info(request):
    if request.user.is_authenticated:
        uid = request.user.id
        user_profile = UserProfile.objects.get(user_id=uid)
        
        initial_data = {
            'sector': user_profile.sector,
            'organisation': user_profile.organisation,
            'office_address': user_profile.office_address,
            'work_phone': user_profile.work_phone,
            'work_email': user_profile.work_email,
            'ipa_number': user_profile.ipa_number,
            'tin_number': user_profile.tin_number,

        }
        
        if request.method == 'POST':
            organisationInfoUpdateForm = OrganisationInfoUpdateForm(request.POST)
            if  organisationInfoUpdateForm.is_valid():
                user_profile.sector = organisationInfoUpdateForm.cleaned_data['sector']
                user_profile.organisation = organisationInfoUpdateForm.cleaned_data['organisation']
                user_profile.office_address = organisationInfoUpdateForm.cleaned_data['office_address']
                user_profile.work_phone = organisationInfoUpdateForm.cleaned_data['work_phone']
                user_profile.work_email = organisationInfoUpdateForm.cleaned_data['work_email']
                user_profile.ipa_number = organisationInfoUpdateForm.cleaned_data['ipa_number']
                user_profile.tin_number = organisationInfoUpdateForm.cleaned_data['tin_number']
                user_profile.save()
               
                messages.success(request, 'Organisation information updated successfully!')
            return redirect('profile')
        else:
            organisationInfoUpdateForm = OrganisationInfoUpdateForm(initial=initial_data)
        return render(request, 'edit_employerinfo.html', {'nav':'profile','form':organisationInfoUpdateForm, })
    return redirect('login_user')

##############
##  PAGES
##############

def public_listing(request):
    clients = ClientProfile.objects.filter(public_listing=True)
    context = {'nav': 'public_listing', 'clients': clients}
    return render(request, 'website/public_listing.html', context)

def about(request):
    return render(request, 'website/about.html')

def contact(request):
    return render(request, 'website/contact.html')

def submit_default_list(request):
    if request.method == 'POST':
        business_name = request.POST.get('business_name')
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        comments = request.POST.get('comments')

        if 'defaults_list' in request.FILES:
            file_name = 'defaults_list'
            upload_type = f'{file_name}'.upper()
            fhandle = request.FILES[f'{file_name}']
            fs_instance = FileSystemStorage()
            renamed = f'{business_name}_{upload_type}_{fhandle.name}'
            filename = fs_instance.save(renamed, fhandle)
            file_url = fs_instance.url(filename)
            db_name = f'submission_spreadsheet_url'

            
            
        
        else:
            file_url = None
            messages.error(request, 'Please upload a file.', extra_tags='danger')
            return render(request, 'website/submit_default_list.html')
        
        DefaultListSubmission.objects.create(
          
            business_name=business_name,
            contact_person = name,
            phone=phone,
            email=email,
            business_address=address,
            comments=comments,
            submission_spreadsheet_url=file_url
            )

        #to send email
        # HTML EMAIL
            
        email_subject = 'NEW Default List Submission'
        
        # HTML EMAIL
        html_content = render_to_string("e_email_temp_general.html", {
            'subject': email_subject,
            'greeting': f'Hi',
            'cta': 'yes',
            'cta_btn1_label': 'View List',
            'cta_btn1_link': f'{file_url}',
            'message': f'You can view and upload the records.',
            'message_details': f'You can view and upload the records.',
            
            'domain': settings.DOMAIN,
            
        })
            
        #########  SENDING EMAIL  #########
        #reply to email
        reply_to_email = 'admin@dc.com.pg'
        sender = 'admin@dc.com.pg'
        cc_list = settings.CC_EMAILS
        bcc_list = settings.BCC_EMAILS
        email_list_one = ['zyakap@outlook.com']
        email_list_two = ['info@dc.com.pg',]
        
        email_list  = email_list_one + email_list_two

        text_content = strip_tags(html_content)
        email = EmailMultiAlternatives(email_subject, text_content, sender,email_list, cc=cc_list, bcc=bcc_list, reply_to=[reply_to_email])
        email.attach_alternative(html_content, "text/html")
        email.attach(fhandle.name, fhandle.read(), fhandle.content_type)
        
        try:
            email.send()
            messages.success(request, "Admin was notified on upload.", extra_tags='info')
        except:
            messages.error(request, "Upload notice was NOT sent to admin.", extra_tags='danger')
            return redirect('admin_dashboard')

        messages.success(request, f'{upload_type} uploaded successfully...')

        return redirect('submit_default_list_feedback')
    
    context = {
        'nav': 'submit_default_list',
        }
    return render(request, 'website/submit_default_list.html', context)

def submit_default_list_feedback(request):
    context = {
        'nav': 'submit_default_list',
        }
    return render(request, 'website/submit_default_list_feedback.html', context)

def request_delist(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        mobile = request.POST.get('mobile')
        email = request.POST.get('email')
        message = request.POST.get('message')

        return redirect('request_delist_feedback')
    context = {
        'nav': 'request_delist'
    }
    return render(request, 'website/request_delist.html', context)

def request_delist_feedback(request):
    context = {
        'nav': 'request_delist',
    }
    return render(request, 'website/request_delist_feedback.html', context)

@csrf_exempt
def newsletter_subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            subscriber, created = Subscriber.objects.get_or_create(email=email)
            if created:
                return JsonResponse({'success': True, 'message': 'You have been subscribed to our newsletter!'})
            else:
                return JsonResponse({'success': False, 'message': 'You are already subscribed to our newsletter.'})
        else:
            return JsonResponse({'success': False, 'message': 'Please provide a valid email address.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

def home(request):
    if request.method == 'POST':
        if request.POST.get('email'):
            email = request.POST.get('email')
            subscriber = Subscriber.objects.create(email=email)
            subscriber.save()
            return JsonResponse({'message': 'Subscriber added successfully'})

    return render(request, 'website/home.html', {'nav': 'home'})

def terms_conditions(request):
    return render(request, 'terms-conditions.html', {'nav': 'terms'})

def messages_user(request):
    uid = request.user.id
    user_profile = UserProfile.objects.get(user_id=uid)
    all_messages = []
    try:
        mylog = UserActivityLog.objects.get(user=user_profile)
        mymsglogs = mylog.msglog
        msgids = list(mymsglogs.split(','))
        for mid in msgids:
            message = Message.objects.get(id=int(mid))
            all_messages.append(message)
    except:
        all_messages = []
    messages_count = len(all_messages)
    return render(request, 'messages_user.html', {'nav':'messages_user', 'all_messages': all_messages, 'messages_count': messages_count })

def credit_rating(request):
    return render(request, 'credit_rating.html', {'nav': 'credit_rating',})

def support(request):
    return render(request, 'support.html', {'nav': 'support',})

def front_search(request):

    query = request.GET.get('qf', '').strip()
    client_results = []
    sme_results = []
    upload_results = []
    address_results = []
    contact_results = []
    employer_results = []
    bank_results = []
    payslip_results = []

    if query:
        client_results = ClientProfile.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(nick_name__icontains=query) |

            Q(email__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(nid_number__icontains=query) |
            Q(passport_number__icontains=query) |
            Q(drivers_license_number__icontains=query) |
            Q(super_member_code__icontains=query) |
            Q(permanent_address__icontains=query)


        )

        sme_results = BusinessProfile.objects.filter(
            Q(trading_name__icontains=query) |
            Q(registered_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(ipa_registration_number__icontains=query) |
            Q(tin_number__icontains=query)
        )

        upload_results = ClientUpload.objects.filter(
            Q(description__icontains=query) |
            Q(upload_type__icontains=query)
        )

        address_results = ClientAddress.objects.filter(
            Q(address__icontains=query) |
            Q(residential_province__icontains=query)
        )

        contact_results = ClientContact.objects.filter(
            Q(email1__icontains=query) |
            Q(email2__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(mobile2__icontains=query)
        )

        employer_results = ClientEmployer.objects.filter(
            Q(employer__icontains=query) |
            Q(job_title__icontains=query) |
            Q(work_email__icontains=query) |
            Q(work_phone__icontains=query) |
            Q(office_address__icontains=query)
        )

        bank_results = ClientBankAccount.objects.filter(
            Q(account_name__icontains=query) |
            Q(account_number__icontains=query)
        )

        payslip_results = Payslip.objects.filter(
            Q(description__icontains=query)
        )

    context = {
        'nav': 'front_search',
        'query': query,
        'client_results': client_results,
        'sme_results': sme_results,
        'upload_results': upload_results,
        'address_results': address_results,
        'contact_results': contact_results,
        'employer_results': employer_results,
        'bank_results': bank_results,
        'payslip_results': payslip_results,
    }

    if not any([client_results, sme_results, upload_results, address_results, contact_results, employer_results, bank_results, payslip_results]):
        context['display_message'] = 'No records found for this search.'

    return render(request, 'website/front_database_search.html', context)


def view_client_record_front(request, client_id):
    client = ClientProfile.objects.get(id=client_id)

    context = {
        'nav': 'front_search',
        'client': client,
    }

    return render(request, 'website/view_client_record.html', context)

##############
##  DATABASE FUNCTIONS
##############
@login_check
def database_overview(request):
    user = request.user
    uid = user.id
    user_profile = UserProfile.objects.get(user_id=uid)

    if request.method == 'POST':
        search_string = request.POST.get('search_string')
        return redirect('database_search_redirect', search_string )

    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)
    
    dcc_records_today = ClientProfile.objects.filter(created_at__gte=today)
    dcc_records_yesterday = ClientProfile.objects.filter(created_at__gte=yesterday).filter(created_at__lte=today)
    dcc_records_today_count = dcc_records_today.count()
    dcc_records_yesterday_count = dcc_records_yesterday.count()
    dcc_updated_today = ClientProfile.objects.filter(updated_at__gte=today)
    dcc_updated_yesterday = ClientProfile.objects.filter(updated_at__gte=yesterday).filter(updated_at__lte=yesterday)
    dcc_updated_today_count = dcc_updated_today.count()
    dcc_updated_yesterday_count = dcc_updated_yesterday.count()


    business_records_today = BusinessProfile.objects.filter(created_at__gte=today)
    business_records_yesterday = BusinessProfile.objects.filter(created_at__gte=yesterday).filter(created_at__lte=today)
    business_records_today_count = business_records_today.count()
    business_records_yesterday_count = business_records_yesterday.count()
    business_updated_today = BusinessProfile.objects.filter(updated_at__gte=today)
    business_updated_yesterday = BusinessProfile.objects.filter(updated_at__gte=yesterday).filter(updated_at__lte=yesterday)
    business_updated_today_count = business_updated_today.count()
    business_updated_yesterday_count = business_updated_yesterday.count()
    

    if (dcc_records_today_count + dcc_records_yesterday_count) != 0:
        dcc_records_percentage_change = (dcc_records_today_count / (dcc_records_today_count + dcc_records_yesterday_count)) * 100
    else:
        dcc_records_percentage_change = 0

    if (dcc_updated_today_count + dcc_updated_yesterday_count) != 0:
        dcc_updated_percentage_change = (dcc_updated_today_count / (dcc_updated_today_count + dcc_updated_yesterday_count)) * 100
    else:
        dcc_updated_percentage_change = 0

    

    if (business_records_today_count + business_records_yesterday_count) != 0:
        business_records_percentage_change = (business_records_today_count / (business_records_today_count + business_records_yesterday_count)) * 100
    else:
        business_records_percentage_change = 0

    if (business_updated_today_count + business_updated_yesterday_count) != 0:
        business_updated_percentage_change = (business_updated_today_count / (business_updated_today_count + business_updated_yesterday_count)) * 100
    else:
        business_updated_percentage_change = 0

    
    
    print(type(dcc_records_today))
    print(dcc_records_today)

    from loan.models import Loan, RecoveryRecord

    business_arrears = Loan.objects.filter(lender=user_profile, funded_category='ACTIVE')
    business_arrears_count = business_arrears.count()
    business_total_arrears = business_arrears.aggregate(total=Sum('total_arrears'))['total'] or 0
    business_defaults = Loan.objects.filter(lender=user_profile, category='FUNDED', status='DEFAULTED')
    business_defaults_count = business_defaults.count()
    business_total_defaults = business_defaults.aggregate(total=Sum('total_outstanding'))['total'] or 0
    business_recovery = Loan.objects.filter(lender=user_profile, funded_category='RECOVERY')
    business_recovery_count = business_recovery.count()
    business_total_recovery = business_recovery.aggregate(total=Sum('total_outstanding'))['total'] or 0

    dcc_arrears = Loan.objects.filter(funded_category='ACTIVE')
    dcc_arrears_count = dcc_arrears.count()
    dcc_total_arrears = dcc_arrears.aggregate(total=Sum('total_arrears'))['total'] or 0
    dcc_defaults = Loan.objects.filter(category='FUNDED', status='DEFAULTED')
    dcc_defaults_count = dcc_defaults.count()
    dcc_total_defaults = dcc_defaults.aggregate(total=Sum('total_outstanding'))['total'] or 0
    dcc_recovery = Loan.objects.filter(funded_category='RECOVERY')
    dcc_recovery_count = dcc_recovery.count()
    dcc_total_recovery = dcc_recovery.aggregate(total=Sum('total_outstanding'))['total'] or 0

    ##recovered

    dcc_client_recovered_today = RecoveryRecord.objects.filter(category='CLIENT', created_at__gt=today)
    dcc_total_client_recovered_today = dcc_client_recovered_today.aggregate(total=Sum('amount'))['total'] or 0
    dcc_client_recovered_yesterday = RecoveryRecord.objects.filter(category='CLIENT', created_at__gt=yesterday)
    dcc_total_client_recovered_yesterday = dcc_client_recovered_yesterday.aggregate(total=Sum('amount'))['total'] or 0

    if (dcc_total_client_recovered_today + dcc_total_client_recovered_yesterday) != 0:
        dcc_client_recovered_percentage_change = (dcc_total_client_recovered_today / (dcc_total_client_recovered_today + dcc_total_client_recovered_yesterday)) * 100
    else:
        dcc_client_recovered_percentage_change = 0
    
    dcc_business_recovered_today = RecoveryRecord.objects.filter(category='BUSINESS', created_at__gt=today)
    dcc_total_business_recovered_today = dcc_business_recovered_today.aggregate(total=Sum('amount'))['total'] or 0
    dcc_business_recovered_yesterday = RecoveryRecord.objects.filter(category='BUSINESS', created_at__gt=yesterday)
    dcc_total_business_recovered_yesterday = dcc_business_recovered_yesterday.aggregate(total=Sum('amount'))['total'] or 0

    if (dcc_total_business_recovered_today + dcc_total_business_recovered_yesterday) != 0:
        dcc_business_recovered_percentage_change = (dcc_total_business_recovered_today / (dcc_total_business_recovered_today + dcc_total_business_recovered_yesterday)) * 100
    else:
        dcc_business_recovered_percentage_change = 0

    context = {
        'domain':domain,
        'nav':'database_overview',
        'user': user_profile,
        'dcc_records_today':dcc_records_today,
        'dcc_records_today_count':dcc_records_today_count,
        'dcc_updated_today':dcc_updated_today,
        'dcc_updated_today_count':dcc_updated_today_count,
       
       
        'business_records_today':business_records_today,
        'business_records_today_count':business_records_today_count,
        'business_updated_today':business_updated_today,
        'business_updated_today_count':business_updated_today_count,
        
       
        'dcc_records_percentage_change':dcc_records_percentage_change,
        'dcc_updated_percentage_change':dcc_updated_percentage_change,
        
        'business_records_percentage_change':business_records_percentage_change,
        'business_updated_percentage_change':business_updated_percentage_change,
        

        'business_total_arrears':business_total_arrears,
        'business_total_defaults':business_total_defaults,
        'business_total_recovery':business_total_recovery,
        
        'dcc_total_arrears':dcc_total_arrears,
        'dcc_total_defaults':dcc_total_defaults,
        'dcc_total_recovery':dcc_total_recovery,
        
        'dcc_arrears_count':dcc_arrears_count,
        'dcc_defaults_count':dcc_defaults_count,
        'dcc_recovery_count':dcc_recovery_count,
        
        'business_arrears_count':business_arrears_count,
        'business_defaults_count':business_defaults_count,
        'business_recovery_count':business_recovery_count,

        'dcc_total_client_recovered_today':dcc_total_client_recovered_today,
        'dcc_total_business_recovered_today':dcc_total_business_recovered_today,
        'dcc_client_recovered_percentage_change':dcc_client_recovered_percentage_change,
        'dcc_business_recovered_percentage_change':dcc_business_recovered_percentage_change,

    }
    return render(request, 'database_overview.html', context)

@login_check
def my_records(request):
    userprofile = UserProfile.objects.get(user_id=request.user.id)
    my_records = ClientProfile.objects.filter(luid=userprofile.luid)

    context = {
        'nav': 'my_records',
        'my_records': my_records,
    }
    
    return render(request, 'my_records.html', context)

@login_check
def client_detail(request, client_id):
    client = get_object_or_404(ClientProfile, id=client_id)
    return render(request, 'dcc_client_detail.html', {'client': client})

@login_check
def database_search(request):
    query = request.GET.get('q', '').strip()
    client_results = []
    sme_results = []
    upload_results = []
    address_results = []
    contact_results = []
    employer_results = []
    bank_results = []
    payslip_results = []

    if query:
        client_results = ClientProfile.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(nick_name__icontains=query) |

            Q(email__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(nid_number__icontains=query) |
            Q(passport_number__icontains=query) |
            Q(drivers_license_number__icontains=query) |
            Q(super_member_code__icontains=query) |
            Q(permanent_address__icontains=query)

        )

        sme_results = BusinessProfile.objects.filter(
            Q(trading_name__icontains=query) |
            Q(registered_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(ipa_registration_number__icontains=query) |
            Q(tin_number__icontains=query)
        )

        upload_results = ClientUpload.objects.filter(
            Q(description__icontains=query) |
            Q(upload_type__icontains=query)
        )

        address_results = ClientAddress.objects.filter(
            Q(address__icontains=query) |
            Q(residential_province__icontains=query)
        )

        contact_results = ClientContact.objects.filter(
            Q(email1__icontains=query) |
            Q(email2__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(mobile2__icontains=query)
        )

        employer_results = ClientEmployer.objects.filter(
            Q(employer__icontains=query) |
            Q(job_title__icontains=query) |
            Q(work_email__icontains=query) |
            Q(work_phone__icontains=query) |
            Q(office_address__icontains=query)
        )

        bank_results = ClientBankAccount.objects.filter(
            Q(account_name__icontains=query) |
            Q(account_number__icontains=query)
        )

        payslip_results = Payslip.objects.filter(
            Q(description__icontains=query)
        )

    context = {
        'nav': 'database_search',
        'query': query,
        'client_results': client_results,
        'sme_results': sme_results,
        'upload_results': upload_results,
        'address_results': address_results,
        'contact_results': contact_results,
        'employer_results': employer_results,
        'bank_results': bank_results,
        'payslip_results': payslip_results,
    }

    if not any([client_results, sme_results, upload_results, address_results, contact_results, employer_results, bank_results, payslip_results]):
        context['display_message'] = 'No records found for this search.'

    return render(request, 'dccdb/database_search.html', context)


@login_check
def database_search_redirect(request, search_string):
    query = search_string
    client_results = []
    sme_results = []
    upload_results = []
    address_results = []
    contact_results = []
    employer_results = []
    bank_results = []
    payslip_results = []

    if query:
        client_results = ClientProfile.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(nick_name__icontains=query) |

            Q(email__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(nid_number__icontains=query) |
            Q(passport_number__icontains=query) |
            Q(drivers_license_number__icontains=query) |
            Q(super_member_code__icontains=query) |
            Q(permanent_address__icontains=query)

        )

        sme_results = BusinessProfile.objects.filter(
            Q(trading_name__icontains=query) |
            Q(registered_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(ipa_registration_number__icontains=query) |
            Q(tin_number__icontains=query)
        )

        upload_results = ClientUpload.objects.filter(
            Q(description__icontains=query) |
            Q(upload_type__icontains=query)
        )

        address_results = ClientAddress.objects.filter(
            Q(address__icontains=query) |
            Q(residential_province__icontains=query)
        )

        contact_results = ClientContact.objects.filter(
            Q(email1__icontains=query) |
            Q(email2__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(mobile2__icontains=query)
        )

        employer_results = ClientEmployer.objects.filter(
            Q(employer__icontains=query) |
            Q(job_title__icontains=query) |
            Q(work_email__icontains=query) |
            Q(work_phone__icontains=query) |
            Q(office_address__icontains=query)
        )

        bank_results = ClientBankAccount.objects.filter(
            Q(account_name__icontains=query) |
            Q(account_number__icontains=query)
        )

        payslip_results = Payslip.objects.filter(
            Q(description__icontains=query)
        )

    context = {
        'nav': 'database_search',
        'query': query,
        'client_results': client_results,
        'sme_results': sme_results,
        'upload_results': upload_results,
        'address_results': address_results,
        'contact_results': contact_results,
        'employer_results': employer_results,
        'bank_results': bank_results,
        'payslip_results': payslip_results,
    }

    if not any([client_results, sme_results, upload_results, address_results, contact_results, employer_results, bank_results, payslip_results]):
        context['display_message'] = 'No records found for this search.'

    return render(request, 'dccdb/database_search.html', context)




