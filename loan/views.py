from django.shortcuts import render
import requests
from .models import Loan
from .serializers import LoanSerializer  # Import your LoanSerializer
from users.models import UserProfile


def get_loans(request, endpoint_url):
    #userprofiles = UserProfile.objects.all()
    #for profile in userprofiles:
        #endpoint_url = profile.endpoint
    #endpoint_url = 'http://127.0.0.1:8000'
    #print(endpoint_url)
    #print(f'{ endpoint_url }/api/loans/')
    endpoint = f'https://{endpoint_url}/api/loans/'
    # Make a GET request to the API endpoint
    print("CAME HERE: NO???")
    try:
        response = requests.get(endpoint, verify=False)
    except:
        return render(request, 'server_running.html')
    print("NOT HERE: NO???")
    print(response)
    if response.status_code == 404:
        error_message = "No New Loans were found."
        return render(request, 'error.html', {'error_message': error_message})
    # Check if the request was successful
    if response.status_code == 200:
        # Extract JSON data from the response
        data = response.json()
        print(data)
        # Check if 'results' key exists in the data
        if data:
            # Use LoanSerializer to deserialize the data into Loan instances
            serializer = LoanSerializer(data=data, many=True)
            # Check if deserialization was successful
            if serializer.is_valid():
                # Save deserialized data into Loan instances
                serializer.save()
                # Retrieve the Loan instances from the database
                loans = Loan.objects.all()
                # Now you have the loans data, you can pass it to the template
                return render(request, 'loan_list.html', {'loans': loans})
            else:
                # Print serializer errors
                print("Serializer errors:", serializer.errors)
                # Handle error if deserialization failed
                error_message = "Failed to deserialize data from the API"
                return render(request, 'error.html', {'error_message': error_message})
        else:
            # Handle error if 'results' key is not found in the data
            error_message = "No New Loans found"
            return render(request, 'error.html', {'error_message': error_message})
    else:
        # Handle error if the request was not successful
        error_message = "Failed to fetch data from the API"
        return render(request, 'error.html', {'error_message': error_message})

    
