from django.shortcuts import render, get_object_or_404
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
    from django.db.models import Sum, Count
    from django.utils import timezone

    users = UserProfile.objects.filter(use_loanmasta=True)
    today_dt = datetime.date.today()
    yesterday_dt = today_dt - datetime.timedelta(days=1)

    # ---- per-tenant activity cards ----
    try:
        userprofile = request.user.userprofile
    except Exception:
        userprofile = None

    def pct(a, b):
        return round((a - b) / b * 100) if b else (100 if a else 0)

    your_records_today = ClientProfile.objects.filter(user_profile=userprofile, created_at__date=today_dt).count() if userprofile else 0
    your_records_yesterday = ClientProfile.objects.filter(user_profile=userprofile, created_at__date=yesterday_dt).count() if userprofile else 0
    your_updated_today = ClientProfile.objects.filter(user_profile=userprofile, updated_at__date=today_dt).count() if userprofile else 0
    your_updated_yesterday = ClientProfile.objects.filter(user_profile=userprofile, updated_at__date=yesterday_dt).count() if userprofile else 0

    from client.models import BusinessProfile
    your_business_today = BusinessProfile.objects.filter(user_profile=userprofile, updated_at__date=today_dt).count() if userprofile else 0
    your_business_yesterday = BusinessProfile.objects.filter(user_profile=userprofile, updated_at__date=yesterday_dt).count() if userprofile else 0

    # ---- DCC-wide stats ----
    dcc_records_today = ClientProfile.objects.filter(created_at__date=today_dt).count()
    dcc_records_yesterday = ClientProfile.objects.filter(created_at__date=yesterday_dt).count()
    dcc_updated_today = ClientProfile.objects.filter(updated_at__date=today_dt).count()
    dcc_updated_yesterday = ClientProfile.objects.filter(updated_at__date=yesterday_dt).count()
    dcc_business_today = BusinessProfile.objects.filter(updated_at__date=today_dt).count()
    dcc_business_yesterday = BusinessProfile.objects.filter(updated_at__date=yesterday_dt).count()

    # ---- loan snapshots ----
    from loan.models import Loan
    dcc_total_arrears = Loan.objects.filter(funded_category='ACTIVE', total_arrears__gt=0).aggregate(s=Sum('total_arrears'))['s'] or 0
    dcc_arrears_count = Loan.objects.filter(funded_category='ACTIVE', total_arrears__gt=0).count()
    dcc_total_defaults = Loan.objects.filter(status='DEFAULTED').aggregate(s=Sum('total_outstanding'))['s'] or 0
    dcc_defaults_count = Loan.objects.filter(status='DEFAULTED').count()
    dcc_total_recovery = Loan.objects.filter(funded_category='RECOVERY').aggregate(s=Sum('total_outstanding'))['s'] or 0
    dcc_recovery_count = Loan.objects.filter(funded_category='RECOVERY').count()

    # ---- DCC cost widget (current month, for this tenant) ----
    dcc_month_cost = None
    if userprofile and userprofile.credit_check_enabled:
        pricing = PricingSettings.current()
        month_logs = ApiUsageLog.objects.filter(
            tenant=userprofile,
            created_at__year=today_dt.year,
            created_at__month=today_dt.month,
        )
        dcc_month_cost = pricing.monthly_base_fee
        for action, _ in ApiUsageLog.ACTION_CHOICES:
            units = month_logs.filter(action=action).aggregate(n=Sum('units'))['n'] or 0
            dcc_month_cost += ApiUsageLog.cost_for(action, units, pricing)

    context = {
        'nav': 'admin_dashboard',
        'users': users,
        'your_records_today_count': your_records_today,
        'your_records_percentage_change': pct(your_records_today, your_records_yesterday),
        'your_updated_today_count': your_updated_today,
        'your_updated_percentage_change': pct(your_updated_today, your_updated_yesterday),
        'your_business_today_count': your_business_today,
        'your_business_percentage_change': pct(your_business_today, your_business_yesterday),
        'dcc_records_today_count': dcc_records_today,
        'dcc_records_percentage_change': pct(dcc_records_today, dcc_records_yesterday),
        'dcc_updated_today_count': dcc_updated_today,
        'dcc_updated_percentage_change': pct(dcc_updated_today, dcc_updated_yesterday),
        'dcc_business_today_count': dcc_business_today,
        'dcc_business_percentage_change': pct(dcc_business_today, dcc_business_yesterday),
        'dcc_total_arrears': dcc_total_arrears,
        'dcc_arrears_count': dcc_arrears_count,
        'dcc_total_defaults': dcc_total_defaults,
        'dcc_defaults_count': dcc_defaults_count,
        'dcc_total_recovery': dcc_total_recovery,
        'dcc_recovery_count': dcc_recovery_count,
        'dcc_month_cost': dcc_month_cost,
        'dcc_enabled': bool(userprofile and userprofile.credit_check_enabled),
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
    query = request.GET.get('q', '').strip()
    clients = ClientProfile.objects.select_related('user_profile').order_by('-updated_at')
    if query:
        clients = clients.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(CUID__icontains=query) |
            Q(LUID__icontains=query) |
            Q(nid_number__icontains=query) |
            Q(mobile1__icontains=query) |
            Q(email__icontains=query) |
            Q(user_profile__organisation__icontains=query)
        )
    context = {
        'nav': 'admin_clients',
        'clients': clients,
        'query': query,
    }
    return render(request, 'admin_clients.html', context)


@admin_check
def admin_client_history(request, client_id):
    """Full audit trail for one tenant's copy of a client, plus every other
    tenant's profile matching the same name — so a DCC operator can see all
    of a person's registrations across tenants (e.g. "Crystal Lama" at 5
    different loanmasta tenants) from one place."""
    client = get_object_or_404(ClientProfile.objects.select_related('user_profile'), pk=client_id)
    history = client.history.all()
    other_profiles = ClientProfile.objects.select_related('user_profile').filter(
        first_name__iexact=client.first_name,
        last_name__iexact=client.last_name,
    ).exclude(pk=client.pk).order_by('-updated_at')
    context = {
        'nav': 'admin_clients',
        'client': client,
        'history': history,
        'other_profiles': other_profiles,
    }
    return render(request, 'admin_client_history.html', context)

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

# ---------------------------------------------------------------------------
# Tenant integration control panel — configure each tenant LMS connection
# (endpoint, LUID, API key, feed toggle) and monitor sync + metered usage.
# ---------------------------------------------------------------------------
from api.models import ApiUsageLog, PricingSettings, CreditCheckAccess, log_usage
from api.sync import sync_tenant
from client.models import ClientCreditScore


@admin_check
def admin_tenants(request):
    tenants = UserProfile.objects.filter(use_loanmasta=True).order_by('organisation')
    context = {
        'nav': 'admin_tenants',
        'tenants': tenants,
    }
    return render(request, 'admin_tenants.html', context)


@admin_check
def admin_tenant_config(request, tenant_id):
    tenant = UserProfile.objects.get(pk=tenant_id)

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'sync_now':
            result = sync_tenant(tenant)
            if result['ok']:
                messages.success(
                    request,
                    f"Sync complete: {result['profiles']} profiles, {result['loans']} loans, "
                    f"{result['statements']} statements.",
                    extra_tags='info')
            else:
                messages.error(request, f"Sync failed: {result['error']}", extra_tags='danger')
            return redirect('admin_tenant_config', tenant_id=tenant.id)

        tenant.endpoint = request.POST.get('endpoint', tenant.endpoint).strip()
        tenant.LUID = request.POST.get('LUID', tenant.LUID).strip()
        if request.POST.get('api_key'):
            tenant.api_key = request.POST.get('api_key').strip()
        tenant.feed_enabled = request.POST.get('feed_enabled') == 'on'
        #subscription plan + what this tenant may view from the credit database
        if request.POST.get('plan') in dict(UserProfile.PLAN_CHOICES):
            tenant.plan = request.POST.get('plan')
        tenant.credit_check_enabled = request.POST.get('credit_check_enabled') == 'on'
        tenant.can_view_loans = request.POST.get('can_view_loans') == 'on'
        tenant.can_view_transactions = request.POST.get('can_view_transactions') == 'on'
        tenant.can_view_uploads = request.POST.get('can_view_uploads') == 'on'
        tenant.save()
        messages.success(request, 'Tenant configuration saved.', extra_tags='info')
        return redirect('admin_tenant_config', tenant_id=tenant.id)

    context = {
        'nav': 'admin_tenants',
        'tenant': tenant,
        'has_key': bool(tenant.api_key),
    }
    return render(request, 'admin_tenant_config.html', context)


@admin_check
def admin_usage_metrics(request):
    """Per-tenant metered usage and cost for a selected month, per DCC pricing."""
    pricing = PricingSettings.current()

    if request.method == 'POST' and request.POST.get('action') == 'save_pricing':
        if pricing.pk is None:
            pricing = PricingSettings()
        for field in ('monthly_base_fee', 'price_per_credit_check',
                      'price_per_profile_lookup', 'price_per_record_synced'):
            value = request.POST.get(field)
            if value not in (None, ''):
                setattr(pricing, field, decimal.Decimal(value))
        pricing.currency = request.POST.get('currency', pricing.currency) or pricing.currency
        pricing.save()
        messages.success(request, 'Pricing updated.', extra_tags='info')
        return redirect('admin_usage_metrics')

    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    logs = ApiUsageLog.objects.filter(created_at__year=year, created_at__month=month)

    rows = []
    grand_total = decimal.Decimal('0.00')
    for tenant in UserProfile.objects.filter(use_loanmasta=True).order_by('organisation'):
        tenant_logs = logs.filter(tenant=tenant)
        usage = {}
        for action, _label in ApiUsageLog.ACTION_CHOICES:
            usage[action] = tenant_logs.filter(action=action).aggregate(n=Sum('units'))['n'] or 0
        cost = pricing.monthly_base_fee
        for action, units in usage.items():
            cost += ApiUsageLog.cost_for(action, units, pricing)
        grand_total += cost
        rows.append({
            'tenant': tenant,
            'credit_checks': usage['CREDIT_CHECK'],
            'lookups': usage['PROFILE_LOOKUP'] + usage['LOANS_LOOKUP'] + usage['TRANSACTIONS_LOOKUP'],
            'feed_records': usage['FEED_SYNC'],
            'cost': cost,
        })

    context = {
        'nav': 'admin_usage_metrics',
        'rows': rows,
        'pricing': pricing,
        'grand_total': grand_total,
        'year': year,
        'month': month,
        'months': [(m, datetime.date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        'years': list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'admin_usage_metrics.html', context)


# ---------------------------------------------------------------------------
# Client detail with DCC credit intelligence (admin view)
# ---------------------------------------------------------------------------

@admin_check
def admin_view_client(request, client_id):
    """Full client record with aggregated DCC credit data.
    Access to the DCC Credit Information section is gated behind a pay-per-view
    overlay: clicking 'View Data' creates a CreditCheckAccess row, logs billing,
    and recomputes the credit score. Access is valid for the tenant's configured
    window (default 12 hours)."""
    from django.utils import timezone
    from django.db.models import Q, Sum

    client = get_object_or_404(ClientProfile.objects.select_related('user_profile'), pk=client_id)
    loans = Loan.objects.filter(owner=client).select_related('lender')

    # Which tenant is viewing this?
    try:
        tenant = request.user.userprofile
    except Exception:
        tenant = None

    dcc_enabled = bool(tenant and tenant.credit_check_enabled)
    dcc_access_valid = False
    dcc_expires_at = None
    dcc_data = None
    credit_score = None

    if dcc_enabled and client.CUID:
        # Check for a live access token
        access = CreditCheckAccess.objects.filter(
            tenant=tenant,
            client_cuid=client.CUID,
            expires_at__gt=timezone.now(),
        ).order_by('-expires_at').first()

        if access:
            dcc_access_valid = True
            dcc_expires_at = access.expires_at

            # Cross-tenant profile matches (same person at other lenders)
            match_q = Q()
            if client.nid_number:
                match_q |= Q(nid_number=client.nid_number)
            if client.first_name and client.last_name:
                match_q |= Q(first_name__iexact=client.first_name,
                             last_name__iexact=client.last_name)
            other_profiles = ClientProfile.objects.filter(match_q).exclude(pk=client.pk) \
                             .select_related('user_profile').order_by('-updated_at')

            all_loans = Loan.objects.filter(owner__in=[client] + list(other_profiles)) \
                            .select_related('lender', 'owner__user_profile').order_by('-created_at')

            loan_summary = all_loans.aggregate(
                total_count=Sum('id') or 0,
                total_borrowed=Sum('amount'),
                total_outstanding=Sum('total_outstanding'),
                total_arrears=Sum('total_arrears'),
            )

            # Retrieve / recompute credit score
            credit_score_obj, _ = ClientCreditScore.objects.get_or_create(client=client)
            credit_score = credit_score_obj

            dcc_data = {
                'other_profiles': other_profiles,
                'all_loans': all_loans,
                'loan_summary': loan_summary,
            }

    context = {
        'nav': 'admin_clients',
        'client': client,
        'loans': loans,
        'dcc_enabled': dcc_enabled,
        'dcc_access_valid': dcc_access_valid,
        'dcc_expires_at': dcc_expires_at,
        'dcc_data': dcc_data,
        'credit_score': credit_score,
        'tenant': tenant,
    }
    return render(request, 'admin_view_client.html', context)


@admin_check
def admin_dcc_credit_access(request, client_id):
    """POST endpoint: grants (or re-uses) a timed credit-check access window,
    logs billing, and recomputes the credit score. Redirects back to the client view."""
    from django.utils import timezone

    if request.method != 'POST':
        return redirect('admin_view_client', client_id=client_id)

    client = get_object_or_404(ClientProfile, pk=client_id)
    try:
        tenant = request.user.userprofile
    except Exception:
        messages.error(request, 'No tenant profile found.', extra_tags='danger')
        return redirect('admin_view_client', client_id=client_id)

    if not tenant.credit_check_enabled:
        messages.warning(request, 'DCC credit checks are disabled for your account.', extra_tags='warning')
        return redirect('admin_view_client', client_id=client_id)

    if not client.CUID:
        messages.warning(request, 'This client has no CUID — cannot log DCC access.', extra_tags='warning')
        return redirect('admin_view_client', client_id=client_id)

    # Re-use an existing live access to avoid double-billing
    existing = CreditCheckAccess.objects.filter(
        tenant=tenant,
        client_cuid=client.CUID,
        expires_at__gt=timezone.now(),
    ).order_by('-expires_at').first()

    if existing:
        messages.info(request, f'DCC access already active — valid until {existing.expires_at:%d %b %Y %H:%M}.', extra_tags='info')
    else:
        window_hours = tenant.credit_check_window_hours or 12
        expires_at = timezone.now() + datetime.timedelta(hours=window_hours)
        CreditCheckAccess.objects.create(
            tenant=tenant,
            client_cuid=client.CUID,
            expires_at=expires_at,
        )
        log_usage(tenant, 'CREDIT_CHECK', detail=client.CUID)
        # Recompute credit score on each new access event
        try:
            score_obj, _ = ClientCreditScore.objects.get_or_create(client=client)
            score_obj.recompute()
        except Exception:
            pass
        messages.success(
            request,
            f'DCC Credit Check unlocked for {window_hours} hours (until {expires_at:%d %b %Y %H:%M}). Billed to your account.',
            extra_tags='info',
        )

    return redirect('admin_view_client', client_id=client_id)


# ---------------------------------------------------------------------------
# DCC Report — per-tenant credit check activity & credit score distribution
# ---------------------------------------------------------------------------

@admin_check
def admin_dcc_report(request):
    """Monthly DCC report: credit check activity, cost per tenant, credit score
    distribution across all clients, and most-accessed clients."""
    from django.db.models import Sum, Count, Avg

    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    pricing = PricingSettings.current()
    logs = ApiUsageLog.objects.filter(created_at__year=year, created_at__month=month)

    # Per-tenant credit check summary
    tenant_rows = []
    grand_total_cost = decimal.Decimal('0.00')
    grand_total_checks = 0
    for tenant in UserProfile.objects.filter(use_loanmasta=True).order_by('organisation'):
        tl = logs.filter(tenant=tenant)
        checks = tl.filter(action='CREDIT_CHECK').aggregate(n=Sum('units'))['n'] or 0
        cost = pricing.monthly_base_fee + ApiUsageLog.cost_for('CREDIT_CHECK', checks, pricing)
        grand_total_cost += cost
        grand_total_checks += checks
        tenant_rows.append({
            'tenant': tenant,
            'checks': checks,
            'cost': cost,
            'enabled': tenant.credit_check_enabled,
        })

    # Credit score distribution
    from client.models import ClientCreditScore
    grade_dist = ClientCreditScore.objects.values('grade').annotate(count=Count('id')).order_by('grade')
    avg_score = ClientCreditScore.objects.aggregate(avg=Avg('score'))['avg'] or 0

    # Most-accessed clients this month
    top_accesses = (
        CreditCheckAccess.objects
        .filter(accessed_at__year=year, accessed_at__month=month)
        .values('client_cuid')
        .annotate(access_count=Count('id'))
        .order_by('-access_count')[:10]
    )
    # Enrich with ClientProfile objects
    top_clients = []
    for row in top_accesses:
        cp = ClientProfile.objects.filter(CUID=row['client_cuid']).first()
        if cp:
            top_clients.append({'client': cp, 'access_count': row['access_count']})

    context = {
        'nav': 'admin_dcc_report',
        'tenant_rows': tenant_rows,
        'grand_total_cost': grand_total_cost,
        'grand_total_checks': grand_total_checks,
        'pricing': pricing,
        'grade_dist': list(grade_dist),
        'avg_score': round(avg_score),
        'top_clients': top_clients,
        'year': year,
        'month': month,
        'months': [(m, datetime.date(2000, m, 1).strftime('%B')) for m in range(1, 13)],
        'years': list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'admin_dcc_report.html', context)


# ---------------------------------------------------------------------------
# Loan detail
# ---------------------------------------------------------------------------

@admin_check
def admin_loan_detail(request, ref):
    """Full detail view for a single loan, looked up by its ref string."""
    loan = get_object_or_404(Loan, ref=ref)
    transactions = loan.transaction_set.all().order_by('-date')
    context = {
        'nav': 'admin_loans',
        'loan': loan,
        'transactions': transactions,
    }
    return render(request, 'admin_loan_detail.html', context)
