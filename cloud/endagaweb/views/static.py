"""Static views -- these are basically our landing pages.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from django import http
from django import template
from django.views.generic import TemplateView, View
import yaml

from endagaweb.models import UserProfile


def attach_profile_and_content_to_context(request, content_path, context):
    """Attaches UserProfile data and yaml content to a request context.

    Args:
      request: a Request instance passed to the View
      content_path: path to our static yaml content
      context: a base context to be modified

    Returns:
      the modified context
    """
    if not request.user.is_anonymous():
        context['user_profile'] = UserProfile.objects.get(user=request.user)
    if content_path:
        with open(content_path) as content_file:
            content = yaml.safe_load(content_file)
        for item in content:
            context[item] = content[item]
    return context


class LandingIndexView(TemplateView):
    """The home page."""
    template_name = "home/endaga.html"


    def get_context_data(self, **kwargs):
        context = super(LandingIndexView, self).get_context_data(**kwargs)
        if not self.request.user.is_anonymous():
            context['user_profile'] = UserProfile.objects.get(user=self.request.user)
        context['quotes'] = [
            "Community Cellular Networks",
            "Tower to the People"
        ]
        return context

class TestView(View):
    def get(self, request, *args, **kwargs):
        return http.HttpResponse('OK')


class InstaFiveHundred(TemplateView):
    """Instantly raise a 500."""

    def get(self, request):
        context = {}
        if not request.user.is_anonymous():
            context['user_profile'] = UserProfile.objects.get(
                user=request.user)
        error_template = template.loader.get_template('500.html')
        html = error_template.render(context, request)
        return http.HttpResponseServerError(html)
