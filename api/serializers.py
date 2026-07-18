from rest_framework import serializers

from client.models import ClientProfile
from loan.models import Loan
from transaction.models import Transaction


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = [
            'CUID', 'LUID', 'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'nid_number', 'credit_rating', 'number_of_loans',
            'number_of_flagged_loans', 'repayment_limit', 'has_loan',
            'dcc_flagged', 'dcc_status', 'dcc_comment',
        ]


class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = [
            'ref', 'UID', 'LUID', 'amount', 'repayment_amount', 'category',
            'funded_category', 'status', 'funding_date', 'number_of_repayments',
            'last_repayment_amount', 'last_repayment_date', 'number_of_defaults',
            'last_default_date', 'last_default_amount', 'days_in_default',
            'total_arrears', 'total_outstanding', 'aging_category',
        ]


class TransactionSerializer(serializers.ModelSerializer):
    loanref = serializers.SlugRelatedField(slug_field='ref', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'ref', 'uid', 'luid', 'loanref', 'date', 'type', 'statement',
            'credit', 'debit', 'arrears', 'balance',
        ]
