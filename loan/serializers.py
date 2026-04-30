from rest_framework import serializers
from .models import Loan

class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = [
            'ref', 'UID', 'LUID', 'amount', 'repayment_amount', 'funded_category',
            'created_at', 'updated_at', 'existing_code', 'lender', 'owner', 'officer',
            'location', 'loan_type', 'classification', 'application_date', 'processing_fee',
            'interest', 'total_loan_amount', 'repayment_frequency', 'number_of_fortnights',
            'category', 'status', 'tc_agreement', 'tc_agreement_timestamp', 'funding_date',
            'repayment_start_date', 'expected_end_date', 'repayment_dates', 'next_payment_date',
            'principal_loan_paid', 'interest_paid', 'default_interest_paid', 'total_paid',
            'fortnights_paid', 'number_of_repayments', 'last_repayment_amount', 'last_repayment_date',
            'number_of_advance_payments', 'last_advance_payment_date', 'last_advance_payment_amount',
            'total_advance_payment', 'advance_payment_surplus', 'number_of_defaults', 'last_default_date',
            'last_default_amount', 'days_in_default', 'total_arrears', 'principal_loan_receivable',
            'ordinary_interest_receivable', 'default_interest_receivable', 'total_outstanding',
            'turnover_days', 'aging_category', 'aging_amount', 'considered_unrecoverable',
            'recovery_date', 'opt1', 'opt2', 'opt3', 'opt4', 'opt5', 'dcc', 'notes'
        ]



