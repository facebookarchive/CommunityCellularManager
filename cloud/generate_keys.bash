#!/bin/bash
#requires easyrsa
easyrsa=/tmp/endaga-easyrsa-tmp
git clone https://github.com/OpenVPN/easy-rsa.git $easyrsa

#create keys for cert
cd certifier
$easyrsa/easyrsa3/easyrsa init-pki
$easyrsa/easyrsa3/easyrsa build-ca nopass
#needed as FPM doesn't build include empty directories in debian packages
touch pki/issued/.emptyfile
touch pki/certs_by_serial/.emptyfile
cp pki/ca.crt etage-bundle.crt

#create keys for openvpn
$easyrsa/easyrsa3/easyrsa gen-req server nopass
$easyrsa/easyrsa3/easyrsa sign server server
$easyrsa/easyrsa3/easyrsa gen-dh
cp pki/private/server.key ../ansible/files/openvpn/etc/openvpn/
cp pki/issued/server.crt ../ansible/files/openvpn/etc/openvpn/
cp pki/ca.crt ../ansible/files/openvpn/etc/openvpn/etage-bundle.crt
cp pki/dh.pem ../ansible/files/openvpn/etc/openvpn/dh2048.pem
cp pki/ca.crt ../../client/conf/registration/etage-bundle.crt

#cleanup
rm -rf $easyrsa
