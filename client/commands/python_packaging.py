"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Fabric commands related to python packaging."""
import imp
import json
import os.path

from fabric.api import cd, env, execute, run
from fabric.context_managers import shell_env
from fabric.contrib.files import exists
from fabric.operations import get
from fabric.operations import put


BASE_DIR = '/home/vagrant/'
COMMON_DIR = '../common'
PKG_DIR = BASE_DIR + 'endaga-packages'


def _prep(path, package_requirements='no'):
    if not exists(path):
        raise Exception('path %s does not exist on the VM, cannot package' %
                        (path, ))
    run('mkdir -p ' + PKG_DIR)  # idempotent
    if package_requirements == 'yes':
        package_install_requirements(path)


def package_python_endaga_core(package_requirements='no',
                               package_common='yes'):
    path = BASE_DIR + 'client'
    _prep(path, package_requirements)
    old_gsmeng = env.gsmeng
    if package_common == 'yes':
        (f, modpath, desc) = imp.find_module('fabfile', [COMMON_DIR])
        if f is not None:
            common = imp.load_module('common_fabfile', f, modpath, desc)
            f.close()
            execute(common.package_common_lib)
        else:
            raise ImportError("unable to load %s/fabfile.py" % (COMMON_DIR, ))
    assert(old_gsmeng == env.gsmeng)
    with cd(path):
        #note flup is a python dep but included here
        #as the pip version breaks compat with python2 --kurtis
        _run_fpm_python(' --deb-pre-depends "postgresql-9.1 | postgresql-9.3 |'
                        ' postgresql-9.4 | postgresql-9.5"'
                        ' --deb-pre-depends postgresql-common'
                        ' --deb-pre-depends "postgresql-client-9.1 |'
                        ' postgresql-client-9.3 | postgresql-client-9.4 |'
                        ' postgresql-client-9.5"'
                        ' --deb-pre-depends postgresql-client-common'
                        ' --depends curl'
                        ' --depends supervisor'
                        ' --depends python3-flup6'
                        ' --after-install'
                        ' /home/vagrant/client/deploy/files/endaga-python-core/postinst'
                        ' --before-install'
                        ' /home/vagrant/client/deploy/files/endaga-python-core/preinst'
                        ' setup.py')


def package_python_sms_utilities(package_requirements='no'):
    """Packages sms_utilities.

    This is on pypi but our client builds will build from source.
    """
    path = BASE_DIR + 'sms_utilities'
    print('packaging %s' % path)
    _prep(path, package_requirements)
    with cd(path):
        _run_fpm_python('setup.py')


def package_python_openbts(package_requirements='no'):
    """Packages openbts-python.

    This is on pypi but we will use debs so that we can enforce a dependency on
    a specific version of openbts.
    """
    path = BASE_DIR + 'openbts-python'
    print('packaging %s' % path)
    _prep(path, package_requirements)
    with cd(path):
        _run_fpm_python('setup.py')
        run('mv *.%s ~/endaga-packages' % env.pkgfmt)

def package_python_osmocom(package_requirements='no'):
    """Packages osmocom-python.

    This is on pypi but we will use debs so that we can enforce a dependency on
    a specific version of osmocom.
    """
    path = BASE_DIR + 'osmocom-python'
    print('packaging %s' % path)
    with cd(path):
        _run_fpm_python('setup.py')


def package_python_snowflake():
    """Packages snowflake.
    """
    print('packaging snowflake from pypi')
    run('mkdir -p ' + PKG_DIR)
    _run_fpm_python('--after-install ' + BASE_DIR +
                    'client/deploy/files/snowflake/postinst snowflake')


def package_python_freeswitch():
    """Builds freeswitch and our fake package with missing python files.

    Freeswitch doesn't properly package some of our python dependencies, so we
    need to package these ourself. Unfortunately the only way to do this is
    build from source and manually hack a package together. See the following
    upstream bugs for more info; once these are resolved we should not need to
    do this anymore:
        https://jira.freeswitch.org/browse/ESL-99
        https://jira.freeswitch.org/browse/FS-5660

    Note this will build freeswitch based on what is currently checked out in
    the local freeswitch repo.  The tag we have used in the past is v1.4.6 and
    the FS repo itself is at https://stash.freeswitch.org/scm/fs/freeswitch.git
    """
    path = BASE_DIR + 'freeswitch'
    _prep(path)
    package_name = 'python-freeswitch-endaga'
    with cd(path):
        version = run('git describe --tags').strip('v')
        run('./bootstrap.sh')
        get(remote_path='modules.conf', local_path='/tmp/modules.conf.orig')
        i = open('/tmp/modules.conf.orig', 'r')
        o = open('/tmp/modules.conf', 'w')
        for line in i:
            if (line.strip().startswith("#languages/mod_python") or
                line.strip().startswith("#applications/mod_esl")):
                o.write(line[1:])
            else:
                o.write(line)
        o.close()
        put(remote_path='modules.conf', local_path='/tmp/modules.conf')
        run('./configure --with-python=`which python3`')
        run('make')

    with cd('%s/libs/esl' % path):
        run('make pymod')

    with cd(path):
        run('fpm'
            ' -n %s'
            ' -s dir'
            ' -t %s'
            ' -v %s'
            ' libs/esl/python/ESL.py=/usr/lib/python3.4/dist-packages/ESL.py'
            ' libs/esl/python/_ESL.so=/usr/lib/python3.4/dist-packages/_ESL.so'
            ' src/mod/languages/mod_python/freeswitch.py='
            '/usr/share/freeswitch/scripts/freeswitch.py' % (
                package_name, env.pkgfmt, version))
        run('mv %s*.%s ~/endaga-packages/' % (package_name, env.pkgfmt))


def package_install_requirements(path):
    """Use FPM's setup metadata library to package dependencies."""
    fpm_path = os.path.split(run('gem which fpm'))
    metadata_pkg_path = os.path.join(fpm_path[0], 'fpm/package')
    with cd(path):
        with shell_env(PYTHONPATH=metadata_pkg_path):
            run('python3 setup.py --command-packages=pyfpm get_metadata '
                '--output=package_metadata.json')
            get(remote_path='package_metadata.json',
                local_path='/tmp/package_metadata.json')
            with open('/tmp/package_metadata.json') as metadata_file:
                package_metadata = json.load(metadata_file)
            for dependency in package_metadata['dependencies']:
                if _run_fpm_python('\'%s\'' % (dependency),
                       warn_only=True).failed:
                    # If this fails, it is likely that this is an Endaga python
                    # package and will be fulfilled from the Endaga repo.
                    print('Ignoring dependency %s' % dependency)
            # We don't want to clobber dependencies built previously.
            run('mv -n *.%s %s' % (env.pkgfmt, PKG_DIR), quiet=True)
            run('rm *.%s' % (env.pkgfmt, ), quiet=True)
            run('rm package_metadata.json')

def _run_fpm_python(command, **kwargs):
    res = run('fpm -s python --verbose '
              '--python-pip pip3 --python-bin python3 '
              '--python-package-name-prefix python3 -t %s %s' %
              (env.pkgfmt, command), **kwargs)
    if res.succeeded:
        run('mv *.%s %s' % (env.pkgfmt, PKG_DIR))
    return res
