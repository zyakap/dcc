#for id_generator
import string
import random

#to send email
from django.conf import settings

from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.html import strip_tags


from urllib import request
from django.shortcuts import render, redirect
from .models import UserProfile
from django.contrib import messages

#admin sender email
sender = settings.DEFAULT_FROM_EMAIL

from django.conf import settings

# id_generator
def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

#FILES UPLOAD
from django.core.files.storage import FileSystemStorage


######################
#START OF FUNCTIONS
######################

##### CHECK STAFF DECORATOR



#to send email
def send_email(self, *content):
    """
    Sends user email with specified parameters
    """
    econtent = []
    for arg in content:
        econtent.append(arg)
        
    subject,greeting,message,details, btn_label, btn_link = econtent[0], econtent[1], econtent[2], econtent[3],  econtent[4], econtent[5]
    domain = settings.DOMAIN
    user = self.user
    subject = econtent[0]
    #email content
    greeting = econtent[1]
    message = econtent[2]
    details = econtent[3]
    btn_label = econtent[4]
    btn_link = econtent[5]

    email_content = render_to_string('custom/email_temp_general.html', {
        'email_subject': subject,
        'greeting': greeting,
        'message': message,
        'message_details': details,
        'action_btn_1': btn_label,
        'action_btn_1_link' : btn_link,
        'user': user,
        'domain': domain,
        
    })
    text_content = strip_tags(email_content)
    email = EmailMultiAlternatives(subject,text_content,sender,['zyakap@outlook.com', 'support@webmasta.com.pg', user.email ])
    email.attach_alternative(email_content, "text/html")

    try: 
        email.send()
        status = 1
    except:
        status = 0

    return status

def email_compilation(request):
    
    #send email to user
    domain = settings.DOMAIN
    
    subject = ''
    ''' if header_cta == 'yes' '''
    cta_label = ''
    cta_link = ''

    greeting = ''
    message = ''
    message_details = ''

    ''' if cta == 'yes' '''
    cta_btn1_label = ''
    cta_btn1_link = ''
    cta_btn2_label = ''
    cta_btn2_link = ''

    ''' if promo == 'yes' '''
    catchphrase = ''
    promo_title = ''
    promo_message = ''
    promo_cta = ''
    promo_cta_link = ''
    
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
    email = EmailMultiAlternatives(subject,text_content,sender,['zyakap@outlook.com', 'support@webmasta.com.pg', user.email ])
    email.attach_alternative(email_content, "text/html")

    try: 
        email.send()
        messages.success(request, "Success Message")
    except:
        messages.error(request, 'Error Message', extra_tags='danger')
        
    return redirect('view_customer', uid)

##### CHECK STAFF DECORATOR
def check_staff(func):
    
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login_user')
    
        staffuser = UserProfile.objects.get(user_id=request.user.id)
        
        if staffuser.category != 'STAFF':
            messages.error(request, "You do not have permission to view this page.", extra_tags="danger")
            return redirect( 'dashboard')
        
        rv = func(request, *args, **kwargs)
        return rv

    return wrapper

##### CHECK STAFF DECORATOR
def admin_check(func):
    
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login_user')
    
        if not request.user.is_superuser:
            messages.error(request, "You do not have permission to view this page.", extra_tags="danger")

            return redirect( 'dashboard')
        
        rv = func(request, *args, **kwargs)
        return rv

    return wrapper

##### Login DECORATOR
def login_check(func):
    
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect('login_user')

        rv = func(request, *args, **kwargs)
        return rv

    return wrapper

##### FILE UPLOAD HANDLER
def fileuploader(request, file_name, user_profile):
    upload_type = f'{file_name}'.upper()
    fhandle = request.FILES[f'{file_name}']
    fs_instance = FileSystemStorage()
    renamed = f'{user_profile.first_name}_{user_profile.last_name}_{upload_type}_{fhandle.name}'
    filename = fs_instance.save(renamed, fhandle)
    file_url = fs_instance.url(filename)
    db_name = f'{file_name}_url'
    setattr(user_profile, db_name, file_url)
    user_profile.save()
    messages.success(request, f'{upload_type} uploaded successfully...')
