"""Crispy form definitions.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime

from django import forms
from django.db.models import Value
from django.db.models.functions import Coalesce
from django.core import urlresolvers
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field
from crispy_forms.bootstrap import StrictButton, FieldWithButtons
from django.contrib.auth.forms import PasswordChangeForm
import pytz

from ccm.common.currency import CURRENCIES
from endagaweb import models
from endagaweb.templatetags import apptags


class UpdateContactForm(forms.Form):
    email = forms.EmailField(required=False, label="Email")
    first_name = forms.CharField(required=False, label="First name")
    last_name = forms.CharField(required=False, label="Last name")
    # Create a list of valid timezone choices.  We want to show the name of the
    # timezone and the UTC offset, e.g. US/Hawaii (UTC-10:00).  The actual
    # choices for these fields are setup as two-tuples where the first value is
    # what is stored in the db and the second is what's displayed.  For the
    # diplayed value, we'll use the same tz-name formatter from the "timezone
    # notice" template. We have to catch non-existent timezones for areas that
    # are undergoing DST transitions when this is called.
    tz_choices = [(tz, apptags.timezone_offset(tz))
                  for tz in pytz.common_timezones]
    timezone = forms.ChoiceField(required=False, label="Timezone",
                                 choices=tz_choices)

    def __init__(self, *args, **kwargs):
        super(UpdateContactForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-updateAccountForm'
        self.helper.form_method = 'post'
        self.helper.form_action = '/account/update'
        self.helper.form_class = 'profile-form'
        self.helper.add_input(Submit('submit', 'Save'))
        self.helper.layout = Layout(
            'email', 'first_name', 'last_name', 'timezone',
        )


class SubscriberInfoForm(forms.Form):
    """Crispy form to set Subscriber name."""
    imsi = forms.CharField(widget=forms.HiddenInput(), required=True)
    name = forms.CharField(required=False, label="Name")
    protect_choices = (
        ('True', 'protect this subscriber from automatic deactivation'),
        ('False', 'allow automatic deactivation (default)'),
    )
    prevent_automatic_deactivation = forms.ChoiceField(
        required=False,
        choices=protect_choices, widget=forms.RadioSelect())

    def __init__(self, *args, **kwargs):
        super(SubscriberInfoForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-SubscriberInfoForm'
        self.helper.form_method = 'post'
        params = {
            'imsi': kwargs.get('initial').get('imsi')
        }
        self.helper.form_action = urlresolvers.reverse(
            'subscriber-edit', kwargs=params)
        # Hide the label for the sub vacuum prevention radio.
        self.fields['prevent_automatic_deactivation'].label = ''
        self.helper.layout = Layout(
            'imsi',
            'name',
            'prevent_automatic_deactivation',
            Submit('submit', 'Save', css_class='pull-right'),
        )


class SubscriberCreditUpdateForm(forms.Form):
    imsi = forms.CharField(widget=forms.HiddenInput(), required=True)
    text = 'You can deduct credits by specifying a negative number.'
    amount = forms.CharField(required=False, label="Amount of Credit",
                             help_text=text)

    def __init__(self, *args, **kwargs):
        super(SubscriberCreditUpdateForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-SubscriberCreditUpdateForm'
        self.helper.form_method = 'post'
        params = {
            'imsi': kwargs.get('initial').get('imsi')
        }
        self.helper.form_action = urlresolvers.reverse(
            'subscriber-adjust-credit', kwargs=params)
        self.helper.form_class = 'col-xs-12 col-md-10 col-lg-8'
        self.helper.layout = Layout(
            'imsi',
            FieldWithButtons('amount',
                             StrictButton('Add', css_class='btn-default',
                                          type='submit')))


class SubscriberSendSMSForm(forms.Form):
    imsi = forms.CharField(widget=forms.HiddenInput(), required=True)
    text = "Maximum 140 characters. The subscriber won't be able to reply."
    message = forms.CharField(required=False, label="Message", max_length=140,
                              help_text=text)

    def __init__(self, *args, **kwargs):
        super(SubscriberSendSMSForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-SubscriberSendSMSForm'
        self.helper.form_method = 'post'
        params = {
            'imsi': kwargs.get('initial').get('imsi')
        }
        self.helper.form_action = urlresolvers.reverse('subscriber-send-sms',
                                                       kwargs=params)
        self.helper.form_class = 'col-xs-12 col-md-8 col-lg-6'
        self.helper.layout = Layout(
            'imsi',
            FieldWithButtons('message',
                             StrictButton('Send', css_class='btn-default',
                                          type='submit')))


class SubscriberSearchForm(forms.Form):
    """Crispy search form on /dashboard/subscribers."""
    query = forms.CharField(required=False, label="")

    def __init__(self, *args, **kwargs):
        self.helper = FormHelper()
        self.helper.form_id = 'id-SearchForm'
        self.helper.form_method = 'get'
        self.helper.form_action = '/dashboard/subscribers'
        self.helper.form_class = 'form-horizontal'
        self.helper.field_class = 'col-xs-12 col-sm-8 col-md-12 col-xl-8'
        search_button = StrictButton('Search', css_class='btn-default',
                                     type='submit')
        self.helper.layout = Layout(FieldWithButtons('query', search_button))
        super(SubscriberSearchForm, self).__init__(*args, **kwargs)


class ChangePasswordForm(PasswordChangeForm):
    """Change password form visible on user profile page."""
    def __init__(self, *args, **kwargs):
        super(ChangePasswordForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-updateAccountForm'
        self.helper.form_method = 'post'
        self.helper.form_action = '/account/password/change'
        self.helper.form_class = 'profile-form'
        self.helper.add_input(Submit('submit', 'Save'))


class NotifyEmailsForm(forms.Form):
    notify_emails = forms.CharField(required=False, label="",
                                    widget=forms.TextInput(attrs={'placeholder': 'shaddi@example.com, damian@example.com'}))
    def __init__(self, *args, **kwargs):
        super(NotifyEmailsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-manage-notify-emails-form'
        self.helper.form_method = 'post'
        self.helper.form_action = '/account/notify_emails/update'
        self.helper.form_class = 'profile-form'
        update_button = StrictButton('Update', css_class='btn-default',
                                     type='submit')
        self.helper.layout =  Layout(FieldWithButtons('notify_emails', update_button))


class NotifyNumbersForm(forms.Form):
    notify_numbers = forms.CharField(required=False, label="",
                                     widget=forms.TextInput(attrs={'placeholder': '+62000000, +52000000, +63000000'}))
    def __init__(self, *args, **kwargs):
        super(NotifyNumbersForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'id-manage-notify-numbers-form'
        self.helper.form_method = 'post'
        self.helper.form_action = '/account/notify_numbers/update'
        self.helper.form_class = 'profile-form'
        update_button = StrictButton('Update', css_class='btn-default',
                                     type='submit')
        self.helper.layout =  Layout(FieldWithButtons('notify_numbers', update_button))


class SubVacuumForm(forms.Form):
    enabled_choices = (
        (True, 'enabled'),
        (False, 'disabled'),
    )
    inactive_help_text = (
        'Subscribers are considered inactive if they have not sent an SMS or'
        ' made an outbound phone call in the time period defined below.'
        ' You can protect a Subscriber from automatic deactivation on the'
        ' subscriber edit page.')
    sub_vacuum_enabled = forms.ChoiceField(
        required=False,
        label='Automatically delete inactive subscribers',
        help_text=inactive_help_text,
        choices=enabled_choices, widget=forms.RadioSelect())
    inactive_days = forms.CharField(
        required=False, label='Outbound inactivity threshold (days)')

    def __init__(self, *args, **kwargs):
        super(SubVacuumForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'inactive-subscribers-form'
        self.helper.form_method = 'post'
        self.helper.form_action = '/dashboard/network/inactive-subscribers'
        # Render the inactive_days field differently depending on whether or
        # not this feature is active.
        if args[0]['sub_vacuum_enabled']:
            days_field = Field('inactive_days')
        else:
            days_field = Field('inactive_days', disabled=True)
        self.helper.layout = Layout(
            'sub_vacuum_enabled',
            days_field,
            Submit('submit', 'Save', css_class='pull-right'),
        )


class NetworkSettingsForm(forms.Form):
    network_name = forms.CharField(required=False, label='Network name')
    choices = [(currency.code, currency.name) for currency in
            CURRENCIES.values()]
    subscriber_currency = forms.ChoiceField(required=False, choices=choices,
                                            label='Subscriber currency')
    choices = (
        ('CA', 'Canada (+1)'),
        ('ID', 'Indonesia (+62)'),
        ('PH', 'Philippines (+63)'),
        ('SE', 'Sweden (+46)'),
        ('US', 'United States (+1)'),
    )
    number_country = forms.ChoiceField(required=False, label='Number country',
                                       choices=choices)
    enabled_choices = (
        (True, 'enabled'),
        (False, 'disabled'),
    )
    autoupgrade_enabled = forms.ChoiceField(
        required=False, label='Automatic tower software upgrades',
        choices=enabled_choices, widget=forms.RadioSelect())
    channel_choices = [(v, v) for v in ('stable', 'beta')]
    autoupgrade_channel = forms.ChoiceField(
        required=False, label='Tower software preference',
        choices=channel_choices)
    in_window_choices = (
        (False, 'as soon as new software is available'),
        (True, 'at a specific time'),
    )
    autoupgrade_in_window = forms.ChoiceField(
        required=False, label='Perform automatic upgrades',
        choices=in_window_choices, widget=forms.RadioSelect())
    autoupgrade_window_start = forms.CharField(
        required=False,
        label='Tower upgrade start time (UTC)')

    def __init__(self, *args, **kwargs):
        super(NetworkSettingsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_id = 'network-settings-form'
        self.helper.form_method = 'post'
        self.helper.form_action = '/dashboard/network/edit'
        # Render the autoupgrade field channel and window fields differently
        # depending on the state of autoupgrade_enabled.
        if args[0]['autoupgrade_enabled']:
            channel_field = Field('autoupgrade_channel')
            in_window_field = Field('autoupgrade_in_window')
            # Render the window-time selection field differently depending on
            # the value of autoupgrade_in_window.
            if args[0]['autoupgrade_in_window']:
                window_field = Field('autoupgrade_window_start')
            else:
                window_field = Field('autoupgrade_window_start', disabled=True)
        else:
            channel_field = Field('autoupgrade_channel', disabled=True)
            in_window_field = Field('autoupgrade_in_window', disabled=True)
            window_field = Field('autoupgrade_window_start', disabled=True)
        self.helper.layout = Layout(
            'network_name',
            'subscriber_currency',
            'number_country',
            'autoupgrade_enabled',
            channel_field,
            in_window_field,
            window_field,
            Submit('submit', 'Save', css_class='pull-right'),
        )


class SelectNetworkForm(forms.Form):
    """Select a Network from a dropdown."""

    def __init__(self, *args, **kwargs):
        super(SelectNetworkForm, self).__init__(*args, **kwargs)
        # We create the choice field here in the init so that if the network
        # values change, the form will pick up the changes and not require the
        # server to be restarted.
        choices = []
        all_networks = models.Network.objects.all()
        for network in all_networks:
            value = network.id
            try:
                user_profile = models.UserProfile.objects.get(network=network)
            except models.UserProfile.DoesNotExist:
                continue
            if user_profile.user.email:
                owner = user_profile.user.email
            else:
                owner = user_profile.user.username
            display = '%s (%s)' % (network.name, owner)
            choices.append((value, display))
        self.fields['network'] = forms.ChoiceField(
            label="Network", choices=choices, required=False)
        # Set layout attributes.
        self.helper = FormHelper()
        self.helper.form_id = 'select-network-form'
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Select'))
        self.helper.layout = Layout('network')


class SelectTowerForm(forms.Form):
    """Select a Tower from a dropdown."""

    def __init__(self, *args, **kwargs):
        super(SelectTowerForm, self).__init__(*args, **kwargs)
        # We create the choice field here in the init so that if the network
        # values change, the form will pick up the changes and not require the
        # server to be restarted.
        choices = []
        # We create a convoluted tower queryset so that towers that have never
        # synced (last_active = None) sort after active and inactive towers.
        the_past = datetime.datetime.now() - datetime.timedelta(days=10*365)
        all_towers = models.BTS.objects.all().annotate(
            new_last_active=Coalesce('last_active', Value(the_past))).order_by(
                '-new_last_active')
        for tower in all_towers:
            value = tower.id
            user_profile = models.UserProfile.objects.get(
                network=tower.network)
            abbreviated_uuid = tower.uuid[0:5]
            if tower.nickname:
                prefix = 'Tower "%s" - %s..' % (
                    tower.nickname, abbreviated_uuid)
            else:
                prefix = 'Tower %s..' % abbreviated_uuid
            display = '%s (%s)' % (prefix, user_profile.user.email)
            choices.append((value, display))
        self.fields['tower'] = forms.ChoiceField(
            label="Tower", choices=choices, required=False)
        # Set layout attributes.
        self.helper = FormHelper()
        self.helper.form_id = 'select-tower-form'
        self.helper.form_method = 'post'
        self.helper.form_action = '/dashboard/staff/tower-monitoring'
        self.helper.add_input(Submit('submit', 'Select'))
        self.helper.layout = Layout('tower')
