import datetime
from decimal import Decimal
import string
import random
import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect
#read excel
from http.client import HTTPResponse
#import pandas as pd

#from accounts.models import User, UserProfile, StaffProfile
#from message.models import Message, MessageLog
#from loan.models import Loan, LoanFile, Statement, Payment
#EMAIL SETTINGS
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.html import strip_tags
#admin sender email

from users.models import UserProfile, ActivityLog
from client.models import ClientProfile, ClientContact, ClientAddress, ClientEmployer, ClientBankAccount
from loan.models import Loan, LoanFile

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# id_generator
def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

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

def admin_upload_client_records_uploader(request, recordsexceldata, userprofile_LUID, _batch=None):
    dbframe = recordsexceldata
    count_loans = 0

    user_profile = UserProfile.objects.get(LUID=userprofile_LUID)

    if _batch is None and not getattr(user_profile, 'use_loanmasta', False):
        from admin1.models import RecordUploadBatch
        _batch = RecordUploadBatch.objects.create(
            uploaded_by=user_profile,
            record_count=len(recordsexceldata),
        )

    for dbframe in dbframe.itertuples():
        #print(dbframe)
        No = dbframe.No
        Customer_Type = dbframe.Customer_Type
        First_Name = dbframe.First_Name
        Last_Name = dbframe.Last_Name
        Middle_Name = dbframe.Middle_Name
        Nick_Name = dbframe.Nick_Name
        Other_Names = dbframe.Other_Names
        Gender = dbframe.Gender
        Date_of_Birth = dbframe.Date_of_Birth
        Marital_Status = dbframe.Marital_Status
        Email_1 = dbframe.Email_1
        Email_2 = dbframe.Email_2
        Mobile_1 = dbframe.Mobile_1
        Mobile_2 = dbframe.Mobile_2
        NID_Number = dbframe.NID_Number
        Passport_Number = dbframe.Passport_Number
        Drivers_License_Number = dbframe.Drivers_License_Number
        Superannuation_Membership_Number = dbframe.Superannuation_Membership_Number
        Place_of_Origin = dbframe.Place_of_Origin
        Province_of_Origin = dbframe.Province_of_Origin
        Permanent_Address = dbframe.Permanent_Address
        Residential_Address = dbframe.Residential_Address
        Residential_Province = dbframe.Residential_Province
        Resident_Owner = dbframe.Resident_Owner
        Postal_Address = dbframe.Postal_Address
        Employer_Name = dbframe.Employer_Name
        Employer_Sector = dbframe.Employer_Sector
        Office_Address = dbframe.Office_Address
        Job_Title = dbframe.Job_Title
        Work_ID_Number = dbframe.Work_ID_Number
        Start_Date = dbframe.Start_Date
        Pay_Frequency = dbframe.Pay_Frequency
        Last_Paydate = dbframe.Last_Paydate
        Gross_Pay = dbframe.Gross_Pay
        Work_Phone = dbframe.Work_Phone
        Work_Email = dbframe.Work_Email
        Bank1_Name = dbframe.Bank1_Name
        Bank1_Branch_Name = dbframe.Bank1_Branch_Name
        Bank1_BSB_Number = dbframe.Bank1_BSB_Number
        Bank1_Account_Name = dbframe.Bank1_Account_Name
        Bank1_Account_Number = dbframe.Bank1_Account_Number
        Bank2_Name = dbframe.Bank2_Name
        Bank2_Branch_Name = dbframe.Bank2_Branch_Name
        Bank2_BSB_Number = dbframe.Bank2_BSB_Number
        Bank2_Account_Name = dbframe.Bank2_Account_Name
        Bank2_Account_Number = dbframe.Bank2_Account_Number
        Notes = dbframe.Notes
        
        Loan_Ref = dbframe.Loan_Ref
        Loan_Type = dbframe.Loan_Type
        Amount = dbframe.Amount
        Funding_Date = dbframe.Funding_Date
        Due_Date = dbframe.Due_Date
        Number_of_Fortnights = dbframe.Number_of_Fortnights
        Repayment_Amount = dbframe.Repayment_Amount
        Total_Loan_Amount = dbframe.Total_Loan_Amount
        Total_Paid = dbframe.Total_Paid
        Total_Outstanding = dbframe.Total_Outstanding
        Loan_Status = dbframe.Loan_Status
        CDB_Listed = dbframe.CDB_Listed

        #create_Client_Profile
        clientprofile = ClientProfile.objects.create(
            user_profile = user_profile,
            client_type = Customer_Type,
            first_name = First_Name,
            last_name = Last_Name,
            gender = Gender,
        )
        clientprofile.save()
        #register activity
        activity_log = ActivityLog.objects.create(
            user_profile = user_profile,
            description = f'Client Profile Created - {First_Name} {Last_Name}',
        )
        activity_log.save()
        #client_prefunctions
        client_count = ClientProfile.objects.all().count()
        this_number = client_count + 1
        first_name_part = First_Name[:2]
        last_name_part = Last_Name[:2]
        initial_DCC = f'DCC{this_number}U{userprofile_LUID}{first_name_part}{last_name_part}'

        clientprofile.initial_dcc = initial_DCC
        clientprofile.CUID = initial_DCC
        clientprofile.LUID = user_profile.LUID
        clientprofile.credit_rating = Decimal(100.00)
        clientprofile.repayment_limit = 0
        # Non-Loanmasta uploads must go through DCC verification
        # before becoming publicly visible. Set vetted=False so they
        # land in the review queue; a VerificationCase is created below.
        is_loanmasta = getattr(user_profile, 'use_loanmasta', False)
        clientprofile.public_search = is_loanmasta
        clientprofile.public_listing = is_loanmasta
        clientprofile.vetted = is_loanmasta
        clientprofile.vetting_status = 'VETTED' if is_loanmasta else 'REVIEW'
        clientprofile.save()

        if not is_loanmasta:
            from admin1.models import VerificationCase
            VerificationCase.objects.get_or_create(
                client=clientprofile,
                defaults={'lender': user_profile, 'batch': _batch},
            )
        
        if Middle_Name and Middle_Name != 'N/A':
            clientprofile.Middle_Name = dbframe.Middle_Name
            activity_log.description = f'Client Profile Created - {First_Name} {Middle_Name} {Last_Name}'
            activity_log.save()
        if Nick_Name and Nick_Name != 'N/A':
            clientprofile.nick_name = dbframe.Nick_Name
            clientprofile.save()
        if Other_Names and Other_Names != 'N/A':
            print('Came Here')
            clientprofile.other_names = dbframe.Other_Names
            clientprofile.save()
        if Gender and Gender != 'N/A':
            clientprofile.gender = dbframe.Gender
            print('Came Here')
            clientprofile.save()
        
        if Date_of_Birth and Date_of_Birth != 'N/A':
            try:
                date_of_birth = pd.to_datetime(Date_of_Birth)
                if pd.isna(date_of_birth):
                    clientprofile.date_of_birth = None
                else:
                    clientprofile.date_of_birth = date_of_birth.date()
            except (ValueError, TypeError):
                clientprofile.date_of_birth = None
        else:
            clientprofile.date_of_birth = None
        clientprofile.save()
        if Marital_Status and Marital_Status != 'N/A':
            clientprofile.marital_status = dbframe.Marital_Status
            clientprofile.save()
        if NID_Number and NID_Number != 'N/A':
            clientprofile.nid_number = dbframe.NID_Number
            clientprofile.save()
        if Passport_Number and Passport_Number != 'N/A':
            clientprofile.passport_number = dbframe.Passport_Number
            clientprofile.save()
        if Drivers_License_Number and Drivers_License_Number != 'N/A':
            clientprofile.drivers_license_number = dbframe.Drivers_License_Number
            clientprofile.save()
        if Superannuation_Membership_Number and Superannuation_Membership_Number != 'N/A':
            clientprofile.superannuation_membership_number = dbframe.Superannuation_Membership_Number
            clientprofile.save()
        if Place_of_Origin and Place_of_Origin != 'N/A':
            clientprofile.place_of_origin = dbframe.Place_of_Origin
            clientprofile.save()
        if Province_of_Origin and Province_of_Origin != 'N/A':
            clientprofile.province_of_origin = dbframe.Province_of_Origin
            clientprofile.save()
        if Permanent_Address and Permanent_Address != 'N/A':
            clientprofile.permanent_address = dbframe.Permanent_Address
            clientprofile.save()
        if Notes and Notes != 'N/A':
            clientprofile.notes = Notes
            clientprofile.save()
        if CDB_Listed and CDB_Listed != 'N/A':
            clientprofile.cdb_comment = CDB_Listed
            clientprofile.save()
        if Email_1 and Email_1 != 'N/A':
            clientprofile.email = dbframe.Email_1
            clientprofile.save()
        if Mobile_1 and Mobile_1 != 'N/A':
            clientprofile.mobile1 = str(Mobile_1)
            clientprofile.save()
        
        
        clientprofile.save()

        if (Email_1 and Email_1 != 'N/A') or (Mobile_1 and Mobile_1 != 'N/A'):
            clientcontact = ClientContact.objects.create(
            client = clientprofile,
            email1 = Email_1 if Email_1 != 'N/A' else None,
            mobile1 = Mobile_1 if Mobile_1 != 'N/A' else None,
            )
            clientcontact.save()
            if Email_2 and Email_2 != 'N/A':
                clientcontact.email2 = Email_2
            if Mobile_2 and Mobile_2 != 'N/A':
                clientcontact.mobile2 = Mobile_2
            clientcontact.save()
                

        if Residential_Address and Residential_Address != 'N/A':
            client_address = ClientAddress.objects.create(
            client = clientprofile,
            address_type = 'RESIDENTIAL',
            address = Residential_Address,
            residential_province = Residential_Province if Residential_Province != 'N/A' else None,
            resident_owner = Resident_Owner if Resident_Owner != 'N/A' else None,
            )
            client_address.save()
        
        if Postal_Address and Postal_Address != 'N/A':
            ClientAddress.objects.create(
            client = clientprofile,
            address_type = 'POSTAL',
            address = Postal_Address,
            )

        if Employer_Name and Employer_Name != 'N/A':
            employer = ClientEmployer.objects.create(
            client = clientprofile,
            employer = Employer_Name,
            )
            employer.save()

            if Employer_Sector and Employer_Sector != 'N/A':
                employer.sector = Employer_Sector
            if Office_Address and Office_Address != 'N/A':
                employer.office_address = Office_Address
                ClientAddress.objects.create(
                    client = clientprofile,
                    address_type = 'OFFICE',
                    address = Office_Address,
                )
            if Job_Title and Job_Title != 'N/A':
                employer.job_title = Job_Title
            if Work_ID_Number and Work_ID_Number != 'N/A':
                employer.work_id_number = Work_ID_Number
            if Start_Date and Start_Date != 'N/A':
                
                try:
                    start_date = pd.to_datetime(Start_Date)
                    if pd.isna(start_date):
                        employer.start_date = None
                    else:
                        employer.start_date = start_date.date()
                except (ValueError, TypeError):
                    employer.start_date = None

            if Pay_Frequency and Pay_Frequency != 'N/A':
                employer.pay_frequency = Pay_Frequency
            if Last_Paydate and Last_Paydate != 'N/A':
                try:
                    last_paydate = pd.to_datetime(Last_Paydate)
                    if pd.isna(last_paydate):
                        employer.last_paydate = None
                    else:
                        employer.last_paydate = last_paydate.date()
                except (ValueError, TypeError):
                    employer.start_date = None
            if Gross_Pay and Gross_Pay != 'N/A':
                try:
                    employer.gross_pay = Decimal(Gross_Pay)
                except (ValueError, TypeError, Decimal.InvalidOperation, InvalidOperation):
                    employer.gross_pay = None
            else:
                employer.gross_pay = None
            employer.save()
            if Work_Phone and Work_Phone != 'N/A':
                employer.work_phone = Work_Phone
            if Work_Email and Work_Email != 'N/A':
                employer.work_email = Work_Email
            employer.save()
        
        if Bank1_Name and Bank1_Name != 'N/A':
            ClientBankAccount.objects.create(
            client = clientprofile,
            bank = Bank1_Name,
            account_name = Bank1_Account_Name if Bank1_Account_Name != 'N/A' else None,
            account_number = Bank1_Account_Number if Bank1_Account_Number != 'N/A' else None,
            branch_bsb = Bank1_BSB_Number if Bank1_BSB_Number != 'N/A' else None,
            branch_name = Bank1_Branch_Name if Bank1_Branch_Name != 'N/A' else None,
            )
        
        if Bank2_Name and Bank2_Name != 'N/A':
            ClientBankAccount.objects.create(
            client = clientprofile,
            bank = Bank2_Name,
            account_name = Bank2_Account_Name if Bank2_Account_Name != 'N/A' else None,
            account_number = Bank2_Account_Number if Bank2_Account_Number != 'N/A' else None,
            branch_bsb = Bank2_BSB_Number if Bank2_BSB_Number != 'N/A' else None,
            branch_name = Bank2_Branch_Name if Bank2_Branch_Name != 'N/A' else None,
            )
        
        #Loan entry
        if Total_Outstanding and Total_Outstanding != 'N/A':
            clientprofile.number_of_loans += 1
            clientprofile.number_of_flagged_loans += 1
            clientprofile.has_loan = True
            clientprofile.dcc_flagged = True
            clientprofile.dcc_comment = 'Record Submitted'
            clientprofile.public_category = Loan_Status
            clientprofile.save()

            loan = Loan.objects.create(
                lender = user_profile,
                owner = clientprofile,
                total_outstanding = Total_Outstanding,
                )
            loan.save()

            #update the loan
            loan.funding_date = Funding_Date
            loan.save()
            loan.amount = Amount
            loan.save()
            loan.number_of_fortnights = Number_of_Fortnights
            loan.save()
            loan.repayment_amount = Repayment_Amount
            loan.save()
            loan.expected_end_date = Due_Date
            loan.save()

            #update loan
            loan.category = 'FUNDED'
            loan.funded_category = 'DEFAULTED'
            loan.status = 'DEFAULTED'
            loan.save()

            today = datetime.date.today()
            days_in_default = (today - Due_Date.date()).days
            loan.days_in_default = days_in_default
            loan.save()

            #activity_log
            activity_log2 = ActivityLog.objects.create(
                user_profile = user_profile,
                description = f'Loan Created - {First_Name} {Last_Name} - {Loan_Ref}',
            )
            activity_log2.save()

            if Middle_Name:
                activity_log2.description = f'Loan Created - {First_Name} {Middle_Name} {Last_Name} - {Loan_Ref}'
                activity_log2.save()

            messages.success(request, f'Client Record - {First_Name} {Last_Name} recorded', extra_tags='secondary')
        
        
            #create the loan
            loanref_prefix = 'DCC'
            upid = user_profile.id
            First_Name = user_profile.first_name
            Last_Name = user_profile.last_name
            rand = random.randint(0,999)
            refx = f'{loanref_prefix}{upid}{First_Name[0]}{Last_Name[0]}{rand}'

            loan_id = loan.id
            str_loan_id = str(loan_id)
            finalref_first_part = refx[:-1]
            final_ref = f'{finalref_first_part}{str_loan_id}'
            loan.ref = final_ref
            loan.uid = refx
            loan.luid = user_profile.LUID
            loan.save()

            loanfile = LoanFile.objects.create(loan=loan)
            loanfile.save()
            count_loans += 1
        
            messages.success(request, f'Loan for {First_Name} {Last_Name} created successfully!')
            
        print(count_loans)
        messages.success(request, f'{count_loans} uploaded successfully!')

        #return 1
        
    

