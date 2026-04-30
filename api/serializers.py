from rest_framework import serializers
from loan.models import Loan
from client.models import ClientProfile
from users.models import UserProfile
from transaction.models import Transaction

class LoanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Loan
        fields = ['ref', 'uid', 'luid', 'amount', 'repayment_amount', 'funded_category']

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['uid', 'luid', 'loanref']

class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ['luid','uid','first_name','last_name','date_of_birth','nid_number','credit_rating','has_loan','in_recovery','default_flagged','dcc_flagged','has_arrears' ]

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['luid', 'organization']