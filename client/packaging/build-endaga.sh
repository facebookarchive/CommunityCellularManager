#!/bin/bash
#
# Copyright (c) 2016-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree. An additional grant
# of patent rights can be found in the PATENTS file in the same directory.
#
#
# Builds the main endaga metapackage via fpm.  Usage:
#   $ package/build-endaga.sh
#   $ package/build-endaga.sh /tmp
#   $ package/build-endaga.sh /tmp openbts
#   $ package/build-endaga.sh /tmp openbts rpm

set -e
BUILD_DATE=`date -u +"%Y%m%d%H%M%S"`
ENDAGA_VERSION="0.8.1"

# The resulting package is placed in $OUTPUT_DIR
# or in the cwd.
if [ -z "$1" ]; then
  OUTPUT_DIR='.'
else
  OUTPUT_DIR=$1
  if [ ! -d "$OUTPUT_DIR" ]; then
    echo "error: $OUTPUT_DIR is not a valid directory. Exiting..."
    exit 1
  fi
fi

#select GSM engine
if [ -z "$2" ]; then
  GSM='openbts'
elif [[ "$2" =~ ^(openbts|osmocom|osmocom-fairwaves)$ ]]; then
  GSM=$2
else
  echo "error: $2 is not a supported GSM Engine. Exiting..."
  exit 2
fi

#select package to build
if [ -z "$3" ]; then
  PKGFMT='deb'
elif [[ "$3" =~ ^(deb|rpm)$ ]]; then
  PKGFMT=$3
else
  echo "error: $3 is not a supported package format. Exiting..."
  exit 2
fi

NAME=endaga-${GSM}_${ENDAGA_VERSION}_all.${PKGFMT}
BUILD_PATH=${OUTPUT_DIR}/$NAME

PACKAGE_DIR=/vagrant/packaging

#remove old packages
if [ -f ${BUILD_PATH} ]; then
  rm ${BUILD_PATH}
fi

#set up appropriate dependencies
if [[ $GSM =~ openbts ]]; then
    PREINST=${PACKAGE_DIR}/endaga-preinst
    POSTINST=${PACKAGE_DIR}/openbts-postinst
    OTHER_DEPS=(
	'--depends' 'openbts-public (= 5.0.8)'
	'--depends' 'sipauthserve-public (= 5.0.1)'
	'--depends' 'smqueue-public (= 5.0.4)'
	'--depends' 'python3-openbts (= 0.1.15)'
	'--depends' 'liba53 (= 0.1)'
	'--depends' 'freeswitch-meta-vanilla (= 1.4.15~1-1~wheezy+1)'
	'--depends' 'freeswitch-mod-python (= 1.4.15~1-1~wheezy+1)'
	'--depends' 'freeswitch-mod-sms (= 1.4.15~1-1~wheezy+1)'
	'--depends' 'freeswitch-mod-esl (= 1.4.15~1-1~wheezy+1)'
	'--depends' 'freeswitch-mod-xml-cdr (= 1.4.15~1-1~wheezy+1)'
	'--depends' 'python-freeswitch-endaga (= 1.4.6)'
	'--depends' 'rsyslog (=8.12.0-0adiscon1trusty1)'
	'--depends' 'rsyslog-mmnormalize (=8.12.0-0adiscon1trusty1)'
	'--conflicts' 'endaga-osmocom'
  '--conflicts' 'endaga-osmocom-fairwaves'
	)
elif [[ $GSM =~ osmocom ]]; then
    PREINST=${PACKAGE_DIR}/endaga-preinst
    POSTINST=${PACKAGE_DIR}/osmocom-postinst
    OTHER_DEPS=(
	'--depends' 'openggsn (>= 0.92)'
	'--depends' 'osmocom-nitb (>= 0.14.0)'
	'--depends' 'osmo-sip-connector'
	'--depends' 'osmo-trx (>= 0.1.9)'
	'--depends' 'osmo-pcu (>= 0.2)'
	'--depends' 'osmocom-sgsn (>= 0.15.0)'
	'--depends' 'python3-osmocom (>= 0.1.0)'
  '--depends' 'python-esl'
  '--depends' 'freeswitch-meta-vanilla'
	'--depends' 'freeswitch-mod-python'
	'--depends' 'freeswitch-mod-sms'
	'--depends' 'freeswitch-mod-smpp'
	'--depends' 'freeswitch-mod-esl'
	'--depends' 'freeswitch-mod-xml-cdr'
	'--depends' 'rsyslog (>= 7.4)'
	'--depends' 'uhd-host (>= 3.7.3-1)'
	)

  if [[ $GSM =~ osmocom-fairwaves ]]; then
    OTHER_DEPS+=(
      '--depends' 'osmo-bts (>= 0.2.9) | osmo-bts-trx (>= 0.2.9)'
      '--conflicts' 'endaga-openbts'
      '--conflicts' 'endaga-osmocom'
    )
  else
    OTHER_DEPS+=(
      '--depends' 'osmo-bts-trx (>= 0.5.0)'
      '--conflicts' 'endaga-openbts'
      '--conflicts' 'endaga-osmocom-fairwaves'
    )
  fi
fi

#build it
fpm \
    -s dir \
    -t $PKGFMT \
    -a all \
    --name endaga-${GSM} \
    --provides 'endaga' \
    --conflicts 'endaga' \
    --replaces 'endaga' \
    --package ${BUILD_PATH} \
    --description 'Community Cellular Manager client software' \
    --version ${ENDAGA_VERSION} \
    --after-install ${POSTINST} \
    --before-install ${PREINST} \
    --license "BSD" \
    --maintainer "CommunityCellularManager@fb.com" \
    --depends "endaga-lang (= 0.2.3)" \
    --depends "freeswitch-conf-endaga (= 0.3.5)" \
    --depends "libpq-dev" \
    --depends "lighttpd" \
    --depends "openvpn" \
    --deb-pre-depends "python3-endaga-core (= 0.6.1)" \
    --depends "python3-psycopg2" \
    --depends "python3-snowflake (= 0.0.3)" \
    --depends "postgresql" \
    --depends "postgresql-contrib" \
    --depends "sqlite3" \
    "${OTHER_DEPS[@]/#/}" \
    -C ${PACKAGE_DIR}/${GSM} \
    .
