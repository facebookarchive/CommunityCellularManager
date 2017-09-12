"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

"""Fabric commands related to shipping packages to our package repo."""

import getpass
import time

from fabric.api import execute
from fabric.api import hosts
from fabric.api import local
from fabric.api import run
from fabric.api import env
from fabric.operations import get
from fabric.operations import put
from fabric.operations import sudo
from fabric.operations import prompt

def _get_packages():
    """Get all the packages from a remote machine and put them in a local temp
    deploy directory.
    """
    local('mkdir -p /tmp/endaga-packages-deploy')
    get(remote_path='~/endaga-packages/*.%s' % env.pkgfmt,
        local_path='/tmp/endaga-packages-deploy/')
    local('ls /tmp/endaga-packages-deploy')


@hosts('repo.example.com')
def _push_packages_to_repo(repo_name="dev"):
    """Push local deploy directory of packages to actual repo, and refresh the
    repo.
    """
    if env.pkgfmt != "deb":
        # We only support freight, which is only for deb packages. We'd need to
        # add something that understands RPM repos as well if we want to add
        # support for CentOS here.
        print("Only pushing deb packages is supported, not pushing.")
        return
    run('mkdir -p /tmp/endaga-packages-deploy')
    put(local_path='/tmp/endaga-packages-deploy/*.deb',
        remote_path='/tmp/endaga-packages-deploy/')
    sudo('freight add /tmp/endaga-packages-deploy/*.deb apt/%s' % repo_name)
    sudo('freight cache apt/%s' % repo_name)
    run('rm -r /tmp/endaga-packages-deploy')


def _cleanup_package_deploy():
    """Delete local temp deploy directory."""
    local('rm -r /tmp/endaga-packages-deploy')


def _kirby_dance(wait=5):
    kirby = "<('-'<) ^('-')^ (>'-')> v('-')v".split()
    idx = 0
    while idx < wait:
        print(kirby[idx % len(kirby)])
        time.sleep(1)
        idx += 1


def shipit():
    """Takes packages on a local dev VM and pushes them to repo."""
    if env.pkgfmt != "deb":
        # Since we don't support pushing packages to non-deb repos, just fail
        # early. This can be removed when _push_packages_to_repo has CentOS
        # support.
        print("Only shipping deb packages is supported, not shipping.")
        return

    execute(_get_packages)

    release = prompt('Specify release branch', default='dev',
                     validate='^(dev|test|beta|stable|trusty)$')
    print("HEY! LISTEN! You're about to make a release to '%s'." % release)
    print("We'll ship whatever is in /tmp/endaga-packages-deploy!")
    print("Namely, these:")
    local("ls -lrth /tmp/endaga-packages-deploy/*.deb")
    print("This will probably affect lots of users! Think this through!")
    _kirby_dance(8)
    sure = prompt("Are you sure you want to continue (yes/no)?",
                  default="no", validate='^(yes|no)$')
    if sure != "yes":
        exit()
    print("Releasing to '%s'." % release)
    execute(_push_packages_to_repo, release)
    execute(_cleanup_package_deploy)


@hosts('repo.example.com')
def promote_metapackage(version, from_repo, to_repo):
    """Move a metapackage (and its deps) between repos.

    This will enforce the flow of packages from dev -> test -> beta -> stable
    (and not, say, dev -> stable).  It will also run the necessary freight
    commands so packages in the new repo are available.

    This assumes deb_pkg_tools and scripts/copy_metapackage_and_deps are
    installed on repo.endaga.

    usage: fab dev promote_metapackage:version=0.4.2,from_repo=dev,to_repo=beta
    """
    if env.pkgfmt != "deb":
        print("Only shipping deb packages is supported, not shipping.")
        return

    # Validate first.
    valid_repos = ('trusty', 'dev', 'test', 'beta', 'stable')
    if from_repo not in valid_repos or to_repo not in valid_repos:
        raise ValueError('invalid repo name')
    if valid_repos.index(from_repo) + 1 != valid_repos.index(to_repo):
        raise ValueError('cannot move packages between these repos')
    # Move metapackage and deps to a tmp dir on repo.endaga.
    tmp_path = '/tmp/metapackage-and-deps-for-%s' % to_repo
    run('mkdir -p %s' % tmp_path)
    sudo('copy_metapackage_and_deps %s %s %s' % (version, from_repo, tmp_path))
    sudo('freight add %s/*.deb apt/%s' % (tmp_path, to_repo))
    sudo('freight cache apt/%s' % to_repo)
    run('rm -rf %s' % tmp_path)
