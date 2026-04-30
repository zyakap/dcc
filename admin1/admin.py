from django.contrib import admin
from .models import DelistRequest, DelistRequestFeedback, Subscriber, DefaultListSubmission

@admin.register(DelistRequest)
class DelistRequestAdmin(admin.ModelAdmin):
    list_display = ('name_of_requester', 'email_of_requester', 'phone_of_requester', 'date', 'is_approved', 'is_delisted')
    search_fields = ('name_of_requester', 'email_of_requester', 'phone_of_requester')
    list_filter = ('is_approved', 'is_delisted', 'date')
    readonly_fields = ('date', 'approved_date', 'feedback_date')

@admin.register(DelistRequestFeedback)
class DelistRequestFeedbackAdmin(admin.ModelAdmin):
    list_display = ('profile', 'delist_request', 'date')
    search_fields = ('profile__user__email', 'delist_request__name_of_requester')
    list_filter = ('date',)
    readonly_fields = ('date',)

@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'date')
    search_fields = ('name', 'email')
    list_filter = ('date',)
    readonly_fields = ('date',)

@admin.register(DefaultListSubmission)
class DefaultListSubmissionAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'contact_person', 'email', 'phone', 'date', 'is_approved')
    search_fields = ('business_name', 'contact_person', 'email', 'phone')
    list_filter = ('is_approved', 'date')
    readonly_fields = ('date', 'approved_date', 'feedback_date')
