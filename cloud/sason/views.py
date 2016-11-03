"""sason views.

/sason/* -- Handlers for sason spectrum management

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""
import json

from django.shortcuts import render
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D 
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from endagaweb.models import BTS

RANGE = 10 #km

POWER_LEVEL = 100 #dbm?

class Ping(APIView):
    
    def get(self, request):
        return Response("Sason is working", status=status.HTTP_200_OK)

class Request(APIView):
    
    def post(self, request):
        if not (request.POST.get('uuid') and
                request.POST.get('long') and
                request.POST.get('lat') and
                request.POST.get('bands')
        ):
            return Response("Missing arguments", status=status.HTTP_406_NOT_ACCEPTABLE)
            
        req_bands = request.POST.get('bands').split(',')
        for band in req_bands:
            if not (band in BTS.bands):
                return Response("Invalid Arguments", status=status.HTTP_400_BAD_REQUEST)

        pnt = GEOSGeometry(Point(float(request.POST.get('long')),
                                 float(request.POST.get('lat'))))

        with transaction.atomic():
            tower = BTS.objects.get(uuid=request.POST.get('uuid'))
            nearby_towers = BTS.objects.filter(
                location__distance_lt=(pnt,D(km=RANGE))).exclude(uuid=request.POST.get('uuid'))
            used_channels = dict.fromkeys(BTS.bands.keys(), set())
            for tower in nearby_towers:
                if (tower.band): #skip those without set bands
                    used_channels[tower.band].add(tower.channel)
            free_channels = dict.fromkeys(req_bands)
            for band in req_bands:
                free_channels[band] = BTS.bands[band]['valid_values'].difference(used_channels[band])
                if (len(free_channels[band]) > 0): #something available
                    return Response({ band : free_channels[band],
                                      'power_level' : POWER_LEVEL},
                                    status=status.HTTP_200_OK)
            return Response("No Available Bands", status=status.HTTP_404_NOT_FOUND)
            

class Acquire(APIView):
    
    def post(self, request):
        if not (
                request.POST.get('uuid') and
                request.POST.get('lat') and
                request.POST.get('long') and
                request.POST.get('band') and
                request.POST.get('channel') and
                request.POST.get('power_level')
        ):
            return Response("Missing Arguments", status=status.HTTP_406_NOT_ACCEPTABLE)
        
        if not (
                request.POST.get('band') in BTS.bands and
                request.POST.get('channel').isdigit() and
                request.POST.get('power_level').isdigit()
        ):
            return Response("Invalid Arguments", status=status.HTTP_400_BAD_REQUEST)

        pnt = GEOSGeometry(Point(float(request.POST.get('long')),
                                 float(request.POST.get('lat'))))

        with transaction.atomic():
            tower = BTS.objects.get(uuid=request.POST.get('uuid')) 
            nearby_towers = BTS.objects.filter(
                location__distance_lt=(pnt,D(km=RANGE))).filter(
                    band=request.POST.get('band')).exclude(uuid=request.POST.get('uuid'))
            for t in nearby_towers:
                if (int(request.POST.get('channel')) == t.channel):
                    return Response("Channel In Use", status=status.HTTP_409_CONFLICT)
            #no one interfered
            tower.channel = int(request.POST.get('channel'))
            tower.location = pnt
            tower.band = request.POST.get('band')
            tower.save()
            return Response("Success", status=status.HTTP_200_OK)
