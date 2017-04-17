echo 'deb http://repo.etagecom.io dev main' > /target/etc/apt/sources.list.d/repo_etagecom_io.list
echo 'deb http://repo.endaga.com dev main' > /target/etc/apt/sources.list.d/repo_endaga_com.list
echo 'deb http://download.opensuse.org/repositories/network:/osmocom:/nightly/Debian_8.0 ./' > /target/etc/apt/sources.list.d/opensuse_osmocom.list
cp /cdrom/preseed/endaga-preferences /target/etc/apt/preferences.d/endaga-preferences
cp /cdrom/preseed/osmocom-preferences /target/etc/apt/preferences.d/osmocom-preferences
wget -qO /target/var/opt/pubkey.gpg http://repo.etagecom.io/pubkey.gpg
in-target apt-key add /var/opt/pubkey.gpg
rm /target/var/opt/pubkey.gpg
wget -qO /target/var/opt/pubkey.gpg http://repo.endaga.com/pubkey.gpg
in-target apt-key add /var/opt/pubkey.gpg
rm /target/var/opt/pubkey.gpg
wget -qO /target/var/opt/Release.key http://download.opensuse.org/repositories/network:/osmocom:/nightly/Debian_8.0/Release.key
in-target apt-key add /var/opt/Release.key
rm /target/var/opt/Release.key
