"""Register our models for use in the admin site.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from guardian.admin import GuardedModelAdmin


from endagaweb import models


def delete_user_profile_card_info(modeladmin, request, queryset):
    for user_profile in queryset:
        user_profile.delete_card()
delete_user_profile_card_info.short_description = (
    "Delete card info from user's account.")


class UserProfileAdmin(admin.ModelAdmin):
    actions = [delete_user_profile_card_info]


# Unregister the typical User model.
admin.site.unregister(User)


# Setup a custom User admin model with an email address field.
class UserAdminWithEmail(UserAdmin):
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'email', 'password1', 'password2')
            },
        ),
    )

class BTSLogfileAdmin(admin.ModelAdmin):
    list_display_links = None
    readonly_fields = ('task_id','status')
    list_display = ('status', 'requested', 'bts', 'log_name', 'window_start', 'window_end', 'logfile')
    fieldsets = (
        ('Log selection', {'fields': ('bts', 'log_name')}),
        ('Debug window', {'fields': ('window_start', 'window_end')}))

# Register the custom User admin.
admin.site.register(User, UserAdminWithEmail)
# Register the other models.
admin.site.register(models.BillingTier)
admin.site.register(models.BTS)
admin.site.register(models.ConfigurationKey)
admin.site.register(models.Destination)
admin.site.register(models.DestinationGroup)
admin.site.register(models.Ledger)
admin.site.register(models.Network, GuardedModelAdmin)
admin.site.register(models.NetworkDenomination)
admin.site.register(models.Number)
admin.site.register(models.PendingCreditUpdate)
admin.site.register(models.Subscriber)
admin.site.register(models.Transaction)
admin.site.register(models.UsageEvent)
admin.site.register(models.SystemEvent)
admin.site.register(models.UserProfile, UserProfileAdmin)
admin.site.register(models.BTSLogfile, BTSLogfileAdmin)
admin.site.register(models.FileUpload)
