from django.contrib import admin
from .models import Loan, LoanFile, Statement

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('ref', 'owner', 'amount', 'status', 'funding_date', 'repayment_start_date', 'expected_end_date')
    list_filter = ('status', 'category', 'funded_category', 'loan_type')
    search_fields = ('ref', 'UID', 'LUID', 'owner__user__username')
    ordering = ('-funding_date',)
    fieldsets = (
        ('Loan Details', {
            'fields': ('ref', 'UID', 'LUID', 'existing_code', 'lender', 'owner', 'officer', 'location', 'loan_type', 'classification')
        }),
        ('Financial Information', {
            'fields': ('amount', 'processing_fee', 'interest', 'total_loan_amount', 'repayment_frequency', 'number_of_fortnights', 'repayment_amount')
        }),
        ('Status & Dates', {
            'fields': ('category', 'funded_category', 'status', 'tc_agreement', 'tc_agreement_timestamp', 'funding_date', 'repayment_start_date', 'expected_end_date', 'next_payment_date')
        }),
        ('Repayment Information', {
            'fields': ('principal_loan_paid', 'interest_paid', 'default_interest_paid', 'total_paid', 'fortnights_paid', 'number_of_repayments', 'last_repayment_amount', 'last_repayment_date')
        }),
        ('Default & Arrears', {
            'fields': ('number_of_defaults', 'last_default_date', 'last_default_amount', 'days_in_default', 'total_arrears')
        }),
    )

@admin.register(LoanFile)
class LoanFileAdmin(admin.ModelAdmin):
    list_display = ('loan', 'application_form', 'terms_conditions', 'payslip1', 'bank_statement')
    search_fields = ('loan__ref', 'loan__owner__user__username')
    ordering = ('-created_at',)

@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    list_display = ('ref', 'uid', 'owner', 'loanref', 'date', 'statement_type', 'credit', 'debit', 'balance')
    list_filter = ('statement_type', 'date')
    search_fields = ('ref', 'uid', 'loanref__ref', 'owner__user__username')
    ordering = ('-date',)
