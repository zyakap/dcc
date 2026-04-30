from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from client.models import ClientProfile
from loan.models import Loan
from transaction.models import Transaction

from .serializers import ClientProfileSerializer, LoanSerializer, TransactionSerializer

# Create your views here.

@api_view(['GET'])
def get_clientprofile(request, uid):
   client = get_object_or_404(ClientProfile, uid=uid)
   serializer = ClientProfileSerializer(client)
   return Response(serializer.data)

@api_view(['GET','POST'])
def loan_detail(request, loanref):
   loan = get_object_or_404(Loan,ref=loanref)
   serializer = LoanSerializer(loan)
   return Response(serializer.data)

@api_view(['GET'])
def get_client_transactions(request, uid):
   transactions = Transaction.objects.filter(uid=uid)
   serializer = TransactionSerializer(transactions, many=True, context={'request': request})
   return Response(serializer.data)

@api_view(['GET'])
def get_client_loans(request, uid):

   print('CAME HERE TO DCC:')

   try:
      loans = Loan.objects.filter(uid=uid)
      serializer = LoanSerializer(loans, many=True, context={'request': request})

      print('PRINTING SERIALIZER')
      print(serializer)
      print('printing serializer data')
      print(serializer.data)

      return Response(serializer.data)
   
   except Exception as e:
      return Response({'error': str(e)}, status=500)