#!/bin/sh
#
# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.

# script to generate XML CDR fixtures as expected by unit tests

PATH_TO_CMD=`dirname ${PWD}/${0} | sed -e 's%/./%/%g'`
BASE=${PATH_TO_CMD%cloud/endagaweb/tests/fixtures}
export PYTHONPATH=$BASE/common

GEN_CDR=$PYTHONPATH/scripts/gen_cdr
OUTDIR=`dirname ${0}`

# Unit tests expect the following two numbers to be associated with users,
# i.e., they are the in-network numbers.
USER1="+6285574719464"
USER2="+6285574719465"

# Use a specific external number so that outgoing call cost is predictable
EXTERNAL="+6285603097357"

# Generate 3 fixtures:
#  * intra-network call: USER1 to USER2
#  * incoming: EXTERNAL to USER1 (or USER2)
#  * outgoing: USER1 (or USER2) to EXTERNAL

$GEN_CDR -c $USER1 -d $USER2 >$OUTDIR/bts_to_bts.cdr.xml
$GEN_CDR -c $EXTERNAL -d $USER1 >$OUTDIR/cloud_to_bts.cdr.xml
$GEN_CDR -c $USER1 -d $EXTERNAL >$OUTDIR/bts_to_cloud.cdr.xml
