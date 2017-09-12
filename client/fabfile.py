"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Tasks for setting up and building our client software."""

import re

from fabric.api import cd, local, env, run
from fabric.operations import sudo

# pylint: disable=unused-import
from commands.config_packaging import package_endaga_lang_config
from commands.config_packaging import package_freeswitch_config
from commands.python_packaging import package_python_endaga_core
from commands.python_packaging import package_python_openbts
from commands.python_packaging import package_python_osmocom
from commands.python_packaging import package_python_sms_utilities
from commands.python_packaging import package_python_freeswitch
from commands.external_packaging import package_freeswitch
from commands.translating import compile_lang
from commands.translating import extract_pot
try:
    from commands.fb_shipping import promote_metapackage
    from commands.fb_shipping import shipit
except ImportError:
    from commands.shipping import promote_metapackage
    from commands.shipping import shipit

# Global packaging settings
# Use 'setdefault' so as not to override prior settings, e.g., --set foo=bar
env.setdefault("pkgfmt", "deb")
env.setdefault("gsmeng", "openbts")
env.setdefault("depmap", {})


def get_vagrant_conf(vm):
    vm_conf = local('vagrant ssh-config %s' % (vm, ), capture=True)
    params = {}
    for line in vm_conf.split('\n'):
        vm_param = re.match('^ +(HostName|User|Port|IdentityFile) (.*)', line)
        if vm_param:
            # update expects a sequence of pairs, groups() is a pair
            params.update((vm_param.groups(), ))
    return (params["HostName"],
            params["Port"],
            params["User"],
            # some installations seem to have quotes around the file location
            params["IdentityFile"].strip('"'))


def dev():
    """ Host config for local Vagrant VM. """
    host, port, user, identity_file = get_vagrant_conf(env.gsmeng)
    env.hosts = ['%s@%s:%s' % (user, host, port)]

    # add Vagrant identity file to any values passed on command line
    if env.key_filename is None:
        env.key_filename = []  # no values passed
    env.key_filename.append(identity_file)


def lab():
    """ Host config for real hardware, lab version (i.e., default login). """
    env.hosts = ['endaga@192.168.1.25']
    env.password = 'endaga'

def centos():
    """
    Package things for CentOS (experimental)
    env.pkgfmt: The package format to produce as output
    env.depmap: A mapping between Ubuntu package names and CentOS ones.

    TODO(shasan): The dependency map should handle more than just the package
    name; it should optionally also handle version numbers as well for system
    packages. Ideally, it should also read this in from a file, rather than
    being hardcoded here.
    """
    env.pkgfmt = "rpm"
    env.depmap = {
    }


def ubuntu():
    """
    Package things for Ubuntu (default)
    """
    env.pkgfmt = "deb"
    env.depmap = {
    }

def osmocom():
    """
    Build Osmocom packages
    """
    env.gsmeng = "osmocom"

def openbts():
    """
    Build OpenBTS packages (default)
    """
    env.gsmeng = "openbts"

def package(package_requirements='yes', flavor=''):
    """Build packages for all Endaga-specific software.

    If you just changed one package, run that particular package command.
    """
    # Setup a location for storing all of the packages.
    run('mkdir -p ~/endaga-packages')
    print('current contents of ~/endaga-packages:')
    run('ls ~/endaga-packages')

    if (env.gsmeng == "openbts"):
        package_python_openbts(package_requirements)
    elif (env.gsmeng == "osmocom"):
        package_python_osmocom(package_requirements)
        package_freeswitch()

    # Make .debs on the VM for all python code.
    package_python_sms_utilities(package_requirements)

    # Make a .deb for config files.
    package_freeswitch_config()
    package_endaga_lang_config()
    # Make the core.
    package_python_endaga_core(package_requirements)
    # Make the metapackage.
    package_endaga(flavor)
    print('packaging complete.')


def package_endaga(flavor=''):
    """Builds the endaga metapackages."""
    run('mkdir -p ~/endaga-packages')
    path = '~/client'

    if not flavor: flavor = env.gsmeng

    with cd(path):
        run('packaging/build-endaga.sh ~/endaga-packages %s %s' %
                (flavor, env.pkgfmt))


def update(flush_cache='yes'):
    """ Installs all the packages in ~/endaga-packages.

    Conceptually, think of this step as taking the dpkg files generated in the
    packaging process and running `gedbi` on all of them. While gdebi would
    resolve dependencies for packages, there's an edge case it doesn't handle
    -- specifically, a package that's not in your package repo sources but *is*
    available locally. This happens, for example, when you've created a new
    package and just added it as a dependency. To get around this, we create a
    local apt repo and put the packages in there. That puts it in our repo
    sources so gedbi can resolve new dependencies.
    """
    bin_path = 'dists/localdev/main/binary-i386'
    if (env.gsmeng == "osmocom"):
        bin_path = 'dists/localdev/main/binary-amd64'

    with cd('~/endaga-packages'):
        if flush_cache == 'yes':
            # Clean local repo cache and rebuild
            run('rm -rf %s || exit 0' % bin_path)
            run('mkdir -p %s' % bin_path)
            run('apt-ftparchive packages . '
                '> %s/Packages' % bin_path)
            with cd('%s' % bin_path):
                run('gzip -c Packages > Packages.gz')
                run('apt-ftparchive '
                    '-o APT::FTPArchive::Release::Components=main release . '
                    '> Release')
            with cd('dists/localdev/'):
                run('apt-ftparchive '
                    '-o APT::FTPArchive::Release::Codename=localdev '
                    '-o APT::FTPArchive::Release::Components=main release . '
                    '> Release')
            # Update sources
            run('sudo apt-get update')
        # Install while pinning to localdev repo
        run('for filename in *.deb; do echo y '
            '| sudo gdebi --option=APT::Default-Release=localdev --option=Dpkg::Options::="--force-overwrite" -q $filename '
            '|| exit 1;  done')
    sudo('service lighttpd restart')
    sudo('service freeswitch restart')
