"""
Api utility functions.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from endagaweb import models

def get_network_from_user(user):
    """The API can be called from the dashboard using a Django
    user session or from a BTS. Dashboard requests come from a user
    with a UserProfile while BTS requests come from a Network's auth_user.
    We return the correct network based on the user being used.
    """
    try:
        return models.Network.objects.get(auth_user=user)
    except models.Network.DoesNotExist:
        up = models.UserProfile.objects.get(user=user)
        return up.network


