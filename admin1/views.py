from django.shortcuts import render
from users.models import User, UserProfile
from client.models import ClientProfile
from loan.models import Loan
from transaction.models import Transaction
from .functions import admin_upload_client_records_uploader
from .models import DefaultListSubmission

import datetime
import decimal
import random
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site

from django.db.models import Sum

#TOKENIZER
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode
#from .tokens import loan_tc_agreement_token
from django.core.files.storage import FileSystemStorage

from .functions import id_generator, login_check, admin_check, check_staff

from django.template.loader import render_to_string
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.html import strip_tags

from django.db.models import Q

#FILES UPLOAD
from django.core.files.storage import FileSystemStorage

domain = settings.DOMAIN
domain_dns = settings.DOMAIN_DNS

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
import subprocess

import pandas as pd


def generate_pdf(templatefile, data):
    # Load the template
    env = Environment(loader=FileSystemLoader('custom/templates'))
    template = env.get_template(templatefile)
    # Render the template with the data
    html = template.render(data)
    result = html
    
    # Create the PDF
    pdf = subprocess.Popen(['wkhtmltopdf', '-', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    pdf_data, _ = pdf.communicate(html.encode('utf-8'))
    #pdf_data = pdf_data.encode('latin1', 'ignore')
    return pdf_data

# Create your views here.

@admin_check
def admin_dashboard(request):
    users = UserProfile.objects.filter(use_loanmasta=True)
    context = {
        'nav': 'admin_dashboard',
        'users': users,
    }
    return render(request, 'admin_dashboard.html', context)

@admin_check
def admin_users(request):
    users = UserProfile.objects.filter(use_loanmasta=True)
    context = {
        'nav': 'admin_users',
        'users': users,
    }
    return render(request, 'admin_users.html', context)

@admin_check
def admin_create_user(request):
    if request.method == 'POST':

        organisation = request.POST.get('organisation')
        name = request.POST.get('name')
        email = request.POST.get('email')
        username = request.POST.get('username')
        password = request.POST.get('password')
        LUID = request.POST.get('LUID')
        
        #terms = True
        
        emailexists = User.objects.filter(email=email)
        if len(emailexists) != 0:
            messages.error(request, "There is an account already registered with this email address.", extra_tags='danger')
            return render(request, 'admin_create_user.html')
        
        userexists = User.objects.filter(username=username)
        if len(userexists) != 0:
            messages.error(request, "There is an account already registered with this username.", extra_tags='danger')
            return render(request, 'admin_create_user.html')

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

        userprofile = UserProfile.objects.create(user_id=user.id, first_name=first_name, middle_name=middle_name, last_name=last_name, organisation=organisation, LUID=LUID)
        userprofile.save()

        #to send email
        # HTML EMAIL
            
        email_subject = 'Your DCC account has been created'
        
        # HTML EMAIL
        html_content = render_to_string("e_email_temp_general.html", {
            'subject': email_subject,
            'greeting': f'Hi {first_name}',
            'cta': 'yes',
            'cta_btn1_label': 'VISIT DASHBOARD',
            'cta_btn1_link': f'{settings.DOMAIN}/login_user/',
            'message': f'You can login to your dashboard and start uploading or view default records.',
            'message_details': f'Here are you login details:<br>\
                                    username: {username},<br>\
                                    password: {password}',
            'userprofile': userprofile,
            'domain': settings.DOMAIN,
            
        })
            
        #########  SENDING EMAIL  #########
        #reply to email
        reply_to_email = 'admin@dc.com.pg'
        sender = 'admin@dc.com.pg'
        cc_list = settings.CC_EMAILS
        bcc_list = settings.BCC_EMAILS
        email_list_one = ['zyakap@outlook.com']
        email_list_two = [userprofile.email,]
        
        email_list  = email_list_one + email_list_two

        text_content = strip_tags(html_content)
        email = EmailMultiAlternatives(email_subject, text_content, sender,email_list, cc=cc_list, bcc=bcc_list, reply_to=[reply_to_email])
        email.attach_alternative(html_content, "text/html")
        email.send()
        try:
            email.send()
            messages.success(request, "The account creation notice was sent.", extra_tags='info')
        except:
            messages.error(request, "The account creation notice was NOT sent.", extra_tags='danger')
            return redirect('admin_dashboard')
        
        userprofile = UserProfile.objects.create(email=email, password=password, username=username, is_active=is_active, is_confirmed=is_confirmed, is_dcc_flagged=is_dcc_flagged, is_cdb_flagged=is_cdb_flagged)
        userprofile.save()
        messages.success(request, f"User {username} created", extra_tags="info")
        return redirect('admin_users')
    return render(request, 'admin_create_user.html', {'nav':'admin_create_user',})

@admin_check
def admin_clients(request):
    clients = ClientProfile.objects.all()
    context = {
        'nav': 'admin_clients',
        'clients': clients,
    }
    return render(request, 'admin_clients.html', context)

@admin_check
def admin_loans(request):  

    try:
        referrer = request.META['HTTP_REFERER']
    except:
        host = request.META['HOST']
        pathinfo = request.META['PATH_INFO']
        referrer = f'{host}{pathinfo}'
    
    loans = Loan.objects.all()
    
    #all_loans = Loan.objects.exclude(category='PENDING', funded_category="COMPLETED").all()
    all_loans = loans
    pending_loans = Loan.objects.filter(category="PENDING")
    running_loans = Loan.objects.filter(funded_category="ACTIVE",status="RUNNING")
    defaulted_loans = Loan.objects.filter(funded_category="ACTIVE",status="DEFAULTED")
    completed_loans = Loan.objects.filter(funded_category="COMPLETED")
    recovery_loans = Loan.objects.filter(funded_category="RECOVERY")
    print(recovery_loans)
    
    if request.method=="POST":
        
        if request.POST.get('startdate') and request.POST.get('enddate') and request.POST.get('loantype') and request.POST.get('cuscat'):
            start_date_entry = request.POST.get('startdate')
            end_date_entry = request.POST.get('enddate')
            loantype = request.POST.get('loantype')
            cuscat = request.POST.get('cuscat')

            start_date = start_date_entry 
            end_date = end_date_entry 

            strip_start_date = start_date.split('-')
            strip_end_date = end_date.split('-')

            date_start_date = datetime.date(int(strip_start_date[0]), int(strip_start_date[1]), int(strip_start_date[2]))
            date_end_date = datetime.date(int(strip_end_date[0]), int(strip_end_date[1]), int(strip_end_date[2]))
            
            if date_start_date > date_end_date:
                messages.error(request, 'End date must be after Start date!')
                return redirect('all_loans')

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(loan_type=loantype, owner__category = cuscat, funding_date__gte = start_date, funding_date__lte = end_date).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'cuscat': cuscat, 'loantype': loantype, 'startdate': start_date, 'enddate': end_date,
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }            
            
            return render(request, 'admin_loans.html', context)
        
        elif request.POST.get('startdate') and request.POST.get('enddate') and request.POST.get('loantype'):
            start_date_entry = request.POST.get('startdate')
            end_date_entry = request.POST.get('enddate')
            loantype = request.POST.get('loantype')

            start_date = start_date_entry 
            end_date = end_date_entry

            strip_start_date = start_date.split('-')
            strip_end_date = end_date.split('-')

            date_start_date = datetime.date(int(strip_start_date[0]), int(strip_start_date[1]), int(strip_start_date[2]))
            date_end_date = datetime.date(int(strip_end_date[0]), int(strip_end_date[1]), int(strip_end_date[2]))
            
            if date_start_date > date_end_date:
                messages.error(request, 'End date must be after Start date!')
                return redirect('all_loans')

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(loan_type=loantype, funding_date__gte = start_date, funding_date__lte = end_date).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'loantype': loantype, 'startdate': start_date, 'enddate': end_date,
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }          
            
            return render(request, 'admin_loans.html', context)
        
        elif request.POST.get('startdate') and request.POST.get('enddate') and request.POST.get('cuscat'):
            start_date_entry = request.POST.get('startdate')
            end_date_entry = request.POST.get('enddate')
            cuscat = request.POST.get('cuscat')

            start_date = start_date_entry 
            end_date = end_date_entry

            strip_start_date = start_date.split('-')
            strip_end_date = end_date.split('-')

            date_start_date = datetime.date(int(strip_start_date[0]), int(strip_start_date[1]), int(strip_start_date[2]))
            date_end_date = datetime.date(int(strip_end_date[0]), int(strip_end_date[1]), int(strip_end_date[2]))
            
            if date_start_date > date_end_date:
                messages.error(request, 'End date must be after Start date!')
                return redirect('all_loans')

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(owner__category = cuscat, funding_date__gte = start_date, funding_date__lte = end_date).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'cuscat': cuscat, 'startdate': start_date, 'enddate': end_date,
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }         
                        
            return render(request, 'admin_loans.html', context)
        
        elif request.POST.get('startdate') and request.POST.get('enddate'):
            start_date_entry = request.POST.get('startdate')
            end_date_entry = request.POST.get('enddate')

            start_date = start_date_entry 
            end_date = end_date_entry

            strip_start_date = start_date.split('-')
            strip_end_date = end_date.split('-')

            date_start_date = datetime.date(int(strip_start_date[0]), int(strip_start_date[1]), int(strip_start_date[2]))
            date_end_date = datetime.date(int(strip_end_date[0]), int(strip_end_date[1]), int(strip_end_date[2]))
            
            if date_start_date > date_end_date:
                messages.error(request, 'End date must be after Start date!')
                return redirect('all_loans')

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(funding_date__gte = start_date, funding_date__lte = end_date).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'startdate': start_date, 'enddate': end_date,
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }      
            
            return render(request, 'admin_loans.html', context)
        
        elif request.POST.get('loantype') and request.POST.get('cuscat'): 

            loantype = request.POST.get('loantype')
            cuscat = request.POST.get('cuscat')

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(loan_type=loantype, owner__category = cuscat).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'cuscat': cuscat, 'loantype': loantype,
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }        
            
            return render(request, 'admin_loans.html', context)
        
        elif request.POST.get('loantype'): 
            
            loantype = request.POST.get('loantype')
            

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(loan_type=loantype).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'loantype': loantype, 
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }  
            
            return render(request, 'admin_loans.html', context)
        
        elif request.POST.get('cuscat'): 
            
            cuscat = request.POST.get('cuscat')

            all_loans_filtered = Loan.objects.prefetch_related('owner').filter(owner__category = cuscat).exclude(category='PENDING', funded_category="COMPLETED").all()
            funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
            interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
            totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
            repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
            arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
            defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
            outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
            
            
            context = {
                        'nav' : 'all_loans', 'filter': 'on', 'referrer': referrer,
                        'cuscat': cuscat,
                        'all_loans': all_loans,
                        'all_loans_filtered': all_loans_filtered,
                        'pending_loans': pending_loans,
                        'running_loans':running_loans,
                        'defaulted_loans': defaulted_loans,
                        'completed_loans':completed_loans,
                        'recovery_loans':recovery_loans,
                        'funded_sum': funded_sum,
                        'interests_sum': interests_sum,
                        'totalloan_sum': totalloan_sum,
                        'repayments_sum': repayments_sum,
                        'arrears_sum': arrears_sum,
                        'defaultinterests_sum': defaultinterests_sum,
                        'outstanding_sum': outstanding_sum,       
                        
                    }          
            
            return render(request, 'admin_loans.html', context)
        
        else:
            messages.error(request, 'You did not select any filter', extra_tags='warning')
            return redirect('all_loans')

    #all_loans_filtered = Loan.objects.filter(category="FUNDED").exclude(funded_category="COMPLETED")
    all_loans_filtered = loans
    funded_sum = all_loans_filtered.aggregate(sum=Sum('amount'))['sum']
    interests_sum = all_loans_filtered.aggregate(sum=Sum('interest'))['sum']
    totalloan_sum = all_loans_filtered.aggregate(sum=Sum('total_loan_amount'))['sum']
    repayments_sum = all_loans_filtered.aggregate(sum=Sum('repayment_amount'))['sum']
    arrears_sum = all_loans_filtered.aggregate(sum=Sum('total_arrears'))['sum']
    defaultinterests_sum = all_loans_filtered.aggregate(sum=Sum('default_interest_receivable'))['sum']
    outstanding_sum = all_loans_filtered.aggregate(sum=Sum('total_outstanding'))['sum']
    
    context = {
                'nav' : 'admin_loans', 
                'all_loans': all_loans,
                'all_loans_filtered': all_loans_filtered,
                'pending_loans': pending_loans,
                'running_loans':running_loans,
                'defaulted_loans': defaulted_loans,
                'completed_loans':completed_loans,
                'recovery_loans':recovery_loans,
                'funded_sum': funded_sum,
                'interests_sum': interests_sum,
                'totalloan_sum': totalloan_sum,
                'repayments_sum': repayments_sum,
                'arrears_sum': arrears_sum,
                'defaultinterests_sum': defaultinterests_sum,
                'outstanding_sum': outstanding_sum,       
                
            }  
    
    return render(request, 'admin_loans.html', context)

@admin_check
def admin_transactions(request):
    transactions = Transaction.objects.all()
    context = {
        'nav': 'admin_transactions',
        'transactions': transactions,
    }
    return render(request, 'admin_transactions.html', context)

@admin_check
def admin_retrieve(request):
    users = UserProfile.objects.all()
    context = {
        'users': users,
    }
    return render(request, 'admin_dashboard.html', context)


#actions
#upload client data
@admin_check
def admin_upload_client_records(request):
#try: 
    if request.method == 'POST' and request.FILES['recordsexceldata']:
        userprofile_LUID = request.POST.get('userprofile_luid')   

        recordsexceldata = request.FILES['recordsexceldata']
        fs = FileSystemStorage()
        filename = fs.save(recordsexceldata.name, recordsexceldata)
        uploaded_file_url = fs.url(filename)
        full_path = settings.DOMAIN + uploaded_file_url        
        records_exceldata = pd.read_excel(full_path)
        admin_upload_client_records_uploader(request, records_exceldata, userprofile_LUID)
        messages.success(request, f"ALL DONE", extra_tags="info")
    
    return render(request,'admin_upload_client_records.html',{'nav':'admin_upload_client_records',})

@admin_check
def admin_client_records_under_review(request):
    clients = ClientProfile.objects.filter(vetted=False)
    return render(request,'admin_client_records_under_review.html', {'nav':'admin_client_records_under_review', 'clients':clients})

@admin_check
def admin_business_records_under_review(request):
    return render(request,'admin_business_records_under_review.html', {'nav':'admin_business_records_under_review',})

@admin_check
def admin_default_list_submission(request):
    submissions = DefaultListSubmission.objects.all()
    return render(request,'admin_default_list_submission.html', {'nav':'admin_default_list_submission', 'submissions':submissions})