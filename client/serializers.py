from rest_framework import serializers
from .models import ClientProfile
from users.models import UserProfile

from django.conf import settings

from rest_framework.exceptions import ValidationError

class ClientProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = ClientProfile
        fields = ['LUID', 'CUID', 'first_name', 'last_name']

    def create(self, validated_data):
        # Extract the relevant validated data
        LUID = validated_data.get('LUID')
        CUID = validated_data.get('CUID')
        first_name = validated_data.get('first_name')
        last_name = validated_data.get('last_name')

        # Check if a ClientProfile instance with the same owner, first_name, and last_name already exists
        existing_profile = ClientProfile.objects.filter(LUID=LUID, CUID=CUID, first_name=first_name, last_name=last_name).first()
        
        if existing_profile:
            # If an existing profile is found, return it directly
            return existing_profile
        else:
            # If no existing profile is found, proceed with the default creation process
            print("TRYING TO CREATE USER:")
            return super().create(validated_data)
