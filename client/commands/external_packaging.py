"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Fabric commands for packaging our external software.

External meaning non-python software.
"""
from fabric.api import cd, env, run
from fabric.contrib.files import exists
from fabric.operations import get, put

def package_freeswitch_mod_smpp(fs_version='1.6.9~16~d574870-1~jessie+1'):
    """Builds freeswitch mod_smpp since it isn't shipped by default.
    
    This will build the package based on what is currently checked out in the
    local freeswitc repo. Be sure that the tag that is checked out matches the
    version string that is needed. The tag we have used in the past is v1.6.9 and
    the FS repo itself is at https://stash.freeswitch.org/scm/fs/freeswitch.git

    git clone --branch v1.6.9 https://stash.freeswitch.org/scm/fs/freeswitch.git
    """
    path = '/home/vagrant/freeswitch'
    if not exists(path):
        print 'path %s does not exist on the VM, cannot package' % path
        return
    with cd(path):
        run('git apply ../client/packaging/smpp_reconnect.patch')
        run('./build/set-fs-version.sh %s' % fs_version)
        run('dch -b -m -v "%s" --force-distribution -D unstable "Endaga build."' % fs_version)
        run('./bootstrap.sh', warn_only=True)
        get(remote_path='modules.conf', local_path='/tmp/modules.conf')
        o = open('/tmp/modules.conf', 'a')
        o.write("event_handlers/mod_smpp\n")
        o.close()
	with cd('debian/'):
            put(remote_path='modules.conf', local_path='/tmp/modules.conf')
            run('./bootstrap.sh -c jessie')
        run('sudo mk-build-deps -i -t "apt-get -y --no-install-recommends" debian/control')
        run('dpkg-buildpackage -b -uc')
        run('mkdir -p ~/endaga-packages')
        run('mv ../freeswitch-mod-smpp_%s*.deb ~/endaga-packages/' % fs_version)

def package_sipauthserve(make_clean='no'):
    """Create a deb for sipauthserve (subscriberRegistry).

    The subscriberRegistry repo has its own build script.
    """
    _package_external('/home/vagrant/subscriberRegistry', 'sipauthserve-public', make_clean)


def package_smqueue(make_clean='no'):
    """Create a deb for smqueue.

    The smqueue repo has its own build script which itself calls FPM.
    """
    _package_external('/home/vagrant/smqueue', 'smqueue-public', make_clean)


def package_openbts(make_clean='no'):
    """Create a deb for openbts-public."""
    _package_external('/home/vagrant/openbts', 'openbts-public', make_clean)


def package_liba53(make_clean='no'):
    """Create a deb for liba53."""
    _package_external('/home/vagrant/liba53', 'liba53', make_clean)


def _package_external(directory, package_name, make_clean):
    """Builds packages with mk-build-deps and dpkg-buildpackage.

    Args:
      directory: the path to a repo synced on the VM via vagrant
      package_name: the name of the debian package that will be created
    """
    if env.pkgfmt != "deb":
        print "External packages only support deb, not building."
        return
    if not exists(directory):
        print 'path %s does not exist, cannot package' % directory
        return
    print 'packaging %s as %s' % (directory, package_name)
    run('mkdir -p ~/endaga-packages')
    with cd('/home/vagrant/'):
        with cd(directory):
            run('echo y | sudo mk-build-deps')
            run('sudo gdebi --n %s-build-deps*.deb' % package_name)
            run('rm -f %s-build-deps*.deb' % package_name)
            clean_arg = '' if make_clean == 'yes' else '-nc'
            run('dpkg-buildpackage -b -uc -us %s' % clean_arg)
        run('mv %s_*.deb ~/endaga-packages/.' % package_name)
        run('rm %s_*' % package_name)
