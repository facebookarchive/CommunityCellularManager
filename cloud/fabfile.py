"""
Devops tasks: builds, deployments and migrations.

Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant
of patent rights can be found in the PATENTS file in the same directory.
"""

import datetime
import getpass
import json
import time

from fabric.api import cd, lcd, local, env, run, settings
from fabric.utils import abort, warn, puts


def update_css():
    """ [dev] Recompile CSS """
    with lcd('react-theme/css'):
        local('pwd')
        local('sass theme.scss > compiled/endaga.css')
        local('cp compiled/endaga.css ../../endagaweb/static/css/endaga.css')


def prod():
    """ [deploy] Production deploy settings """
    env.deploy_target = "production"


def staging():
    """ [deploy] Staging deploy settings """
    env.deploy_target = "staging"


def staff():
    """ [deploy] Staff deploy settings """
    env.deploy_target = "staff"


def proxy():
    """ Use SOCKS proxy for ssh from dev servers """
    env.ssh_config_path = "../client/ssh/proxy-config"
    env.use_ssh_config = True


def _is_hg():
    """ Determines if the project is hg controlled """
    try:
        local("hg identify")
        return True
    except:
        return False


def _is_git():
    """ Determines if the project is git controlled """
    try:
        local("git rev-parse")
        return True
    except:
        return False


def _get_versioning_metadata():
    """ Extracts version metadata from the version control system """
    if _is_hg():
        commit_summary = local('hg id -i', capture=True).translate("+")
        # Extract the current branch/bookmark from the bookmarks list.
        bookmarks = local("hg bookmarks", capture=True)
        branch = "master"
        for line in bookmarks.split("\n"):
            if "*" in line:
                branch = line.split()[1]
                break
    elif _is_git():
        branch = local("git rev-parse --abbrev-ref HEAD", capture=True)
        commit_summary = local('git rev-parse HEAD', capture=True).translate(None, "+")
    else:
        raise Exception("Not git or hg")

    # dpkg requires the version start with a number, so lead with `0-`
    version = "0-%s" % commit_summary.split()[0]
    return branch, commit_summary, version


def package():
    """ [deploy] Creates a deployment package. """
    branch, summary, version = _get_versioning_metadata()

    # Builds the deployment package.
    local('fpm -s dir -t deb -n endagaweb -a all -v %(version)s \
            --description "%(branch)s: %(cs)s" \
            -d byobu -d nginx -d python-pip -d python-dev \
            -d libpq-dev -d git -d supervisor \
            --after-install configs/deployment/endagaweb-postinst \
            endagaweb=/var/www ../common/ccm=/var/www \
            requirements.txt=/var/opt/ \
            sason=/var/www settings.py=/var/www urls.py=/var/www \
            manage.py=/var/www/ configs/nginx.conf=/etc/nginx/sites-enabled/ \
            configs/uwsgi.conf=/etc/init/ \
            configs/endagaweb.ini=/etc/uwsgi/apps-enabled/ \
            configs/celeryd.conf=/etc/supervisor/conf.d/ \
            configs/celerybeat.conf=/etc/supervisor/conf.d/ \
            configs/celerystick.conf=/etc/supervisor/conf.d/' \
            % {'branch': branch, 'cs': summary, 'version': version})
    return version


def prepdeploy():
    """ [deploy] Create deploy package and push to S3 """
    local('mkdir -p /tmp/deploydir')
    pkg_version = package()
    pkg_file = "endagaweb_%s_all.deb" % pkg_version
    local('mv %s /tmp/deploydir/endagaweb_all.deb' % pkg_file)
    local('cp -pr configs/deployment/scripts /tmp/deploydir/.')
    local('cp -pr configs/deployment/appspec.yml /tmp/deploydir/.')
    with lcd('/tmp/deploydir'):
        local('zip endagaweb_%s appspec.yml endagaweb_all.deb scripts/*'
              % (pkg_version))
        local('aws s3 cp endagaweb_%s.zip s3://endagaweb-deployment/' % pkg_version)
    local('rm -r /tmp/deploydir')
    puts("Deployment bundle: s3://endagaweb-deployment/endagaweb_%s.zip" % pkg_version)
    return "endagaweb_%s.zip" % pkg_version


def clonedb(original_db, clone_db, region="ap-northeast-1"):
    """ [deploy] Creates a clone of the current production DB.

    Usage from the command line requires fab's special arg syntax, e.g.:
        $ fab clonedb:'staging','test-db-one'
    """
    # Make sure the DB exists first
    output = local("aws rds describe-db-instances --region %s" % region,
                   capture=True)
    instances = json.loads(output)
    orig_instance = None
    for i in instances['DBInstances']:
        if i['DBInstanceIdentifier'] == original_db:
            orig_instance = i
        # Note: we don't else/elif here so we can ensure orig and clone are
        # different.
        if i['DBInstanceIdentifier'] == clone_db:
            abort("Target clone db name '%s' is already in use!" % clone_db)
    if not orig_instance:
        abort("The database '%s' doesn't exist" % original_db)
    # Check that the DB is available.
    if orig_instance["DBInstanceStatus"] != "available":
        abort("The database '%s' is not available, try later. (In state '%s')"
              % (original_db, orig_instance["DBInstanceStatus"]))
    # Generate the various settings we'll use later.
    if len(orig_instance['VpcSecurityGroups']) != 1:
        warn("I don't know how to handle multiple security groups, \
              leaving clone in 'default'.")
    sec_group = orig_instance['VpcSecurityGroups'][0]["VpcSecurityGroupId"]
    datestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    clone_snapshot = "from-%s-for-%s-%s" % (original_db, clone_db, datestamp)
    print(sec_group, clone_snapshot, clone_db, original_db)
    # Create the snapshot.
    puts("Creating DB snapshot '%s', this will take a while." % clone_snapshot)
    cmd = "aws rds create-db-snapshot --db-snapshot-identifier %s \
           --db-instance-identifier %s" % (clone_snapshot, original_db)
    out = local(cmd, capture=True)
    print(out)
    # Spin till the snapshot has been created...
    while True:
        cmd = ("aws rds describe-db-snapshots --db-snapshot-identifier %s"
               % clone_snapshot)
        snapshot = json.loads(local(cmd, capture=True))["DBSnapshots"][0]
        state = snapshot["Status"]
        progress = snapshot["PercentProgress"]
        if state == "available":
            puts("Creating snapshot complete.")
            break
        puts("    %s: %s%% complete" % (state, progress))
        time.sleep(60)
    # Now create the new DB.
    puts("Creating clone DB from snapshot, this'll also take a while.")
    cmd = ("aws rds restore-db-instance-from-db-snapshot \
           --db-snapshot-identifier %s --db-instance-identifier %s \
           --db-instance-class db.t2.large --no-multi-az \
           --db-subnet-group-name main"
           % (clone_snapshot, clone_db))
    out = local(cmd, capture=True)
    puts("Waiting for DB to be created...")
    while True:
        cmd = ("aws rds describe-db-instances --db-instance-identifier %s"
               % clone_db)
        instance = json.loads(local(cmd, capture=True))["DBInstances"][0]
        state = instance["DBInstanceStatus"]
        if state == "available":
            break
        puts("    State: %s" % state)
        time.sleep(60)
    # Update the security group.
    cmd = ("aws rds modify-db-instance --db-instance-identifier %s \
            --vpc-security-group-ids %s" % (clone_db, sec_group))
    out = local(cmd, capture=True)
    # Finally display new DB endpoint info.
    cmd = ("aws rds describe-db-instances --db-instance-identifier %s"
           % clone_db)
    instance = json.loads(local(cmd, capture=True))["DBInstances"][0]
    hostname = instance["Endpoint"]["Address"]
    puts("Your clone DB hostname is '%s'." % hostname)
    puts("Login info is the same as the DB you cloned.")
    puts("Clean up DBs and snapshots when you're done. This shit ain't free.")


def refresh_staging_db():
    """ [deploy] Delete staging DB and clone current prod DB. """
    cmd = ("aws rds delete-db-instance --db-instance-identifier staging \
            --skip-final-snapshot")

    # if this fails, db doesn't exist, so just continue
    with settings(warn_only=True):
        local(cmd, capture=True)

    puts("Waiting for DB to be deleted...")
    while True:
        cmd = "aws rds describe-db-instances --db-instance-identifier staging"
        with settings(warn_only=True):
            # This will keep returning a success until the DB is deleted.
            if local(cmd, capture=True).failed:
                break
        time.sleep(30)
    clonedb("elephant", "staging")


def get_machines(environment=None):
    """ [ops] Get public hostnames for a tier.

    Usage: fab <tier> get_machines
    Example: fab prod get_machines
    """
    if not environment:
        environment = env.deploy_target
    hosts = _get_tier_hostnames(environment)
    for h in hosts:
        print(h)
    return hosts


def deploy(description=None):
    """ [deploy] Make a deployment to an environment. """
    branch, _, _ = _get_versioning_metadata()
    try:
        if env.deploy_target == "production":
            if branch != "master":
                abort("Can't deploy to production from a non-master branch.")
    except AttributeError:
        abort("No deployment target specified.")
    deployment_bundle = prepdeploy()
    if not description:
        now = datetime.datetime.utcnow()
        description = "Deployment of %s at %s UTC" % (deployment_bundle, now)
    # Start the deploy.
    cmd = ("aws deploy create-deployment --application-name=endagaweb \
           --deployment-group-name=endagaweb-%s --description='%s' \
           --s3-location bucket=endagaweb-deployment,key=%s,bundleType=zip"
           % (env.deploy_target, description, deployment_bundle))
    deployment_id = json.loads(local(cmd, capture=True))['deploymentId']

    username = getpass.getuser()
    text = '%s is deploying to `%s` from branch `%s` (bundle: `%s`)' % (
        username, env.deploy_target, branch, deployment_bundle)
    print(text)

    # Now display deployment status until success or failure.
    cmd = ("aws deploy get-deployment --deployment-id %s" % deployment_id)
    while True:
        info = local(cmd, capture=True)
        puts(info)
        status = json.loads(info)["deploymentInfo"]["status"]
        if status in ["Created", "Pending", "InProgress"]:
            time.sleep(10)
            continue
        elif status == "Succeeded":
            # we succeeded. # TODO: replace with IRC
            text = 'deployment to `%s` succeeded (bundle: `%s`)' % (
                env.deploy_target, deployment_bundle)
            print(text)
            break
        else:
            # we failed. TODO: send this message to IRC
            text = 'deployment to `%s` *failed* (bundle: `%s`)' % (
                env.deploy_target, deployment_bundle)
            print(text)
            abort("Deployment %s failed: %s" % (deployment_id, status))


def migrate(application="", migration="", fake_initial=""):
    """[deploy] Perform a database migration.

    Use fake_initial when the db structure already exists -- in old versions of
    Django this was run automatically (see the 1.8 docs for more info).

    Usage:
      fab staging migrate:application=endagaweb,fake_initial=True
    """
    branch, _, _ = _get_versioning_metadata()
    try:
        if env.deploy_target == "production":
            if branch != "master":
                abort("Can't deploy to production from a non-master branch.")
            elif env.deploy_target == "staff":
                abort("Can't migrations the staff env, run on prod instead.")
    except AttributeError:
        abort("No deployment target specified.")
    # Get a machine to ssh into from the specified deployment target.
    host = "ubuntu@%s" % get_machines(env.deploy_target)[0]
    # Run the migration.
    cmd = ("python /var/www/manage.py migrate %s %s --noinput"
           % (application, migration))
    if fake_initial:
        cmd = '%s --fake-initial' % cmd
    with settings(host_string=host):
        with cd("/var/www"):
            result = run("envdir /var/opt/endagaweb-envdir %s" % cmd)
    # tell user how it went
    msg = (("[%s] DB migration to `%s` " % (env.deploy_target, branch)) +
           ("is complete" if result.succeeded else "was unsuccessful"))
    print msg


def restart(service):
    """ [ops] Restart a production service

    Any service managed by supervisord (e.g., celery) can be restarted across
    an entire tier with this.

    Usage: fab <env> restart:<service>
    Example: fab prod restart:celery

    """
    cmd = "sudo supervisorctl restart %s" % service
    tier = env.deploy_target
    hosts = _get_tier_hostnames(tier)
    for h in hosts:
        host = "ubuntu@%s" % h
        with settings(host_string=host):
            result = run(cmd)
            if result.succeeded:
                print("[%s] Restarted %s on %s" % (tier, service, h))
            else:
                print("[%s] Failed to restart %s on %s" % (tier, service, h))

def _get_tier_hostnames(environment):
    cmd = ("aws ec2 describe-instances --filter \
           'Name=tag-key,Values=environment' 'Name=tag-value,Values=%s'"
           % environment)
    res = json.loads(local(cmd, capture=True))
    instances =  []

    for r in res["Reservations"]:
        for i in r:
            if i == "Instances":
                for instance in r[i]:
                   instances.append(instance['PublicDnsName'])
    return instances
