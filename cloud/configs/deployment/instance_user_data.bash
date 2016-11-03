#!/bin/bash

# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

# In AWS, 'user data' is the aptly named optional script that can be run when
# an instance is booted. Things that should go in here are instance-wide
# configuration, like setting up CodeDeploy, logging agents, NewRelic, etc.
# Nothing application-dependent should go in here.  At some point, we can just
# bake an AMI that contains this stuff to make the script smaller.

# Set up Code Deploy so we can do installs
apt-get -y update
apt-get -y install awscli
apt-get -y install ruby2.0
cd /home/ubuntu
aws s3 cp s3://aws-codedeploy-ap-northeast-1/latest/install . --region ap-northeast-1
chmod +x ./install
./install auto

# Get environment now that AWS CLI is set up
# CodeDeploy may not have applied tags when we get here, so we just figure out what autoscaling group we're part of and get the tags that will eventually be applied.
ASGROUP=`aws autoscaling describe-auto-scaling-instances --instance-ids $(wget -q -O - http://169.254.169.254/latest/meta-data/instance-id) --region ap-northeast-1 --output=text | cut -f 2`
DEPLOY_ENV=`aws autoscaling describe-tags --filters Name="auto-scaling-group",Values=$ASGROUP Name=Key,Values=environment --region ap-northeast-1 --output=text | cut -f6`
