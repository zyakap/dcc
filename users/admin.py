
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError


from .models import User, UserProfile, ActivityLog

from .models import UserProfile

from .forms import UserAdminCreationForm, UserAdminChangeForm

User = get_user_model()

# Remove Group Model from admin. We're not using it.

#admin.site.unregister(Group)

class UserAdmin(BaseUserAdmin):
    # The forms to add and change user instances
    
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    
    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    
    list_display = ['email', 'active','admin','confirmed', 'defaulted', 'suspended', 'dcc_flagged', 'cdb_flagged']
    list_filter = ['active','admin','confirmed', 'defaulted', 'suspended', 'dcc_flagged', 'cdb_flagged']
    
    fieldsets = (
        (None, {'fields': ('email','password')}),
        ('Personal Info', {'fields': ()}),
         ('Permissions', {'fields': ('active','admin','confirmed', 'defaulted', 'suspended','dcc_flagged', 'cdb_flagged','groups','user_permissions')}),
         (("Important dates"), {"fields": ('last_login','date_joined')})
    )
    
    # add_fieldsets is not a standard ModelAdmin attribute. UserAdmin
    # overrides get_fieldsets to use this attribute when creating a user.
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
            
        }),
        ('Permissions', {'fields': ('active','admin','confirmed', 'defaulted', 'suspended','dcc_flagged', 'cdb_flagged','groups','user_permissions')}),
    )
    
    search_fields = ['email']
    ordering = ['email']
    filter_horizontal = ('groups','user_permissions')
    
admin.site.register(User, UserAdmin)






class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'organisation', 'first_name', 'last_name', 'mobile1', 'email', 'date_joined')
    list_filter = ('category', 'use_loanmasta')
    search_fields = ('user__email', 'first_name', 'last_name', 'organisation')
    ordering = ('date_joined',)
    
admin.site.register(UserProfile, UserProfileAdmin)

class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user_profile', 'description', 'created_at')
    search_fields = ('user_profile__user__email', 'description')
    ordering = ('-created_at',)
    
admin.site.register(ActivityLog, ActivityLogAdmin)




   


