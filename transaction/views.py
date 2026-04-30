from django.shortcuts import render

import requests
from .models import Transaction
from .serializers import TransactionSerializer  # Import your LoanSerializer

def get_transactions(request, endpoint_url):
    
    endpoint = f'https://{ endpoint_url }/api/statements/'
    # Make a GET request to the API endpoint
    response = requests.get(endpoint, verify=False)

    if response.status_code == 404:
        error_message = "No New Transaction(s) were found."
        return render(request, 'error.html', {'error_message': error_message})
    # Check if the request was successful
    if response.status_code == 200:
        # Extract JSON data from the response
        data = response.json()
        print(data)
        # Check if 'results' key exists in the data
        if data:
            # Use LoanSerializer to deserialize the data into Loan instances
            serializer = TransactionSerializer(data=data, many=True)
            # Check if deserialization was successful
            if serializer.is_valid():
                # Save deserialized data into Loan instances
                serializer.save()
                # Retrieve the Loan instances from the database
                transactions = Transaction.objects.all()
                # Now you have the loans data, you can pass it to the template
                return render(request, 'transaction_list.html', {'transactions': transactions })
            else:
                # Print serializer errors
                print("Serializer errors:", serializer.errors)
                # Handle error if deserialization failed
                error_message = "Failed to deserialize data from the API"
                return render(request, 'error.html', {'error_message': error_message})
        else:
            # Handle error if 'results' key is not found in the data
            error_message = "No New transactions found"
            return render(request, 'error.html', {'error_message': error_message})
    else:
        # Handle error if the request was not successful
        error_message = "Failed to fetch data from the API"
        return render(request, 'error.html', {'error_message': error_message})

