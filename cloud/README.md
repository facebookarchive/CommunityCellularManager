endaga-web
==========

Community Cellular Manager (CCM) web stuff.

Setting up for development
==========================

1) On the machine you're writing code in, set up pip,
[fabric](http://www.fabfile.org/),
[awscli](https://pypi.python.org/pypi/awscli) and
[ansible](http://docs.ansible.com/):

    apt-get install python-pip
    pip install fabric
    pip install awscli
    pip install ansible
    git update-index --assume-unchanged envdir/*

The last command (`git update-index`) allows you to make changes as
necessary to your envdir without worrying about having those changes
checked in. Using this, you can always revert back to the safe
development settings by running `git checkout envdir/`.

2) Generate keys

    ./generate_keys.bash

This will generate a set of keys and certifications for the OpenVPN
and certifier applications.

3) Start Vagrant VMs:

You will also need [Vagrant](http://www.vagrantup.com/downloads.html)
so you can establish a development environment.  Once you've installed
vagrant, just run `vagrant up` and a development box will be created
based on the Vagrantfile in this repo.  This will launch five servers:

`web`
`db` (a PostgreSQL database)
'vpn' (openvpn)
'cert' (a certifier/signing service)
`rmq` (a RabbitMQ broker).

For example, to connect to the VM running the dev environment, you'd
run `vagrant ssh web`.

There is a 6th vm, "smpp" that runs the kannel SMPP service. This is
only needed if you wish to connect to a live SMSC.

The Vagrantfile definition of the 'web' VM uses an Ansible
provisioning step to automatically configure the VM for running Django
within a Python 'virtual environment' (using
[virtualenvwrapper](http://virtualenvwrapper.readthedocs.org/)
for testing and development.

This sets up a virtualenv for you named 'endaga'; the name is
arbitrary, and you can create additional virtualenvs with other names
if you need.

4) On the web VM, use the development environment:

    cd ~/cloud
    workon endaga

The 'endaga' virtual environment MUST be used to run the Django
server; Django is not installed in the root system.

5) Test whether things work:

You can try starting Django (again in the web VM):

    python manage.py makemigrations # only needed the first time to set up db

    python manage.py migrate --noinput  # only needed the first time to set up db

    python manage.py runserver 192.168.40.10:8000

You then can visit the website on the dev (host) web browser at:

    http://192.168.40.10:8000

Note that, unlike the production system, the Django server only runs
when the `runserver` command is executed, i.e., it does not run in the
background. Furthermore, `nginx` is not used as a front-end in the VM;
all static resources are served directly by Django.

6) See the real system in action:

You can create a set of fake users and actions to show in the interface:

    python manage.py setup_test_db

After the db is populated, the log-in name will be "testuser" and
"testpw" on the website.

It's also possible to create an administrative 'super user' account:

    python manage.py createsuperuser

which may be useful for performing certain actions.

7) Connect a development client:

Connecting a development client is detailed in the client README.md

Todo: Also update `local_network_interface` in
`/etc/freeswitch/vars.xml` to use `eth1` since there is no local
openvpn instance and the `external` sip profile will fail to load.

Updating Dependencies
=====================

requirements.txt contains the list of dependencies needed to run
this. Every time you need to add a Python dependency, do it using pip
inside your virtualenv. You can then run `pip freeze >
requirements.txt` at any time to capture the list of Python packages
installed in this virtualevn.

Application Environments
========================

Our application relies on environment variables for its key
configuration parameters; we store these in daemontools-style
envdirs. When you run `manage.py`, it will automatically load settings
from the `envdir` directory in the local directory. We keep these
values configured to match the multi-VM Vagrant setup for local
development. They will not work in production.

Our uWSGI application configuration loads its configuration
information from `/var/opt/endagaweb-envdir`. This is where the
application will load its production settings from. Our production
settings are stored on a directory in S3:
`s3://endagaweb/envdir_prod`. These settings are automatically loaded
onto the server in each deployment. To modify these settings, you can
use standard AWS CLI tools to copy new settings files to that
directory, e.g. `aws cli s3 cp DATABASE_URL
s3://endagaweb/envdir_prod/.` Any changes you've made will take effect
on the next deployment.

Style
=====

We use the [Google Python Style
Guide](https://google-styleguide.googlecode.com/svn/trunk/pyguide.html)
to resolve ambiguity with formatting, whitespace, variable names, etc.

And we strongly recommend using `pylint` before submitting a pull
request. It can catch things beyond style issues -- unused imports,
using `==` instead of `=`, things like that. And there are tons of
editor plugins for emacs, vi, sublime, etc (see
[here](http://docs.pylint.org/ide-integration) for more). Pylint will
be run in "errors-only" mode as a part of our CI tool.

Setup and use is pretty easy, just install the package and the django
plugin. Then run pylint against `endagaweb` with the repo's
`pylintrc`. You can check for errors only and/or style warnings. You
can also run against a specific module you're working on.

```
pip install -r requirements-dev.txt
pylint endagaweb --rcfile=pylintrc
pylint endagaweb --rcfile=pylintrc --errors-only
pylint endagaweb/urls.py --rcfile=pylintrc
```

Workflow
========

Basic workflow rules (it's basically
[this](http://scottchacon.com/2011/08/31/github-flow.html)) and we
happen to also use
[subtrees](https://help.github.com/articles/about-git-subtree-merges/)
for common libs:

- Master branch should always be deployable; never make changes directly to
  master.
- Any changes you want to make should start in their own branch
- Push your branches to GitHub early and often
- When you push a branch to GitHub, [CodeShip](https://codeship.com) will
  automatically run the tests.  Make sure this passes.
- Run `pylint` to check your python for style issues and other possible errors (see notes above).
- Once you're ready to merge into master, issue a pull request onto master via
  github. This is where code review should happen.
- Once you've passed code review, merge the pull request into master.

Subtrees
========

endagaweb/common:
-----------------

Initialization

```
git remote add -f common git@github.com:endaga/common.git
git subtree add --prefix endagaweb/common common master
```

You can pull changes from an upstream branch using the command

```
git subtree pull --prefix endagaweb/common common <branch>
```

You can contribute back to the upstream by pushing directly to the
upstream and pulling or by using the command

```
git subtree push --prefex endagaweb/common common <branch>
```


Deployment
==========

We use [AWS CodeDeploy](http://aws.amazon.com/codedeploy/) for our
deployment. The deployment process is as follows:

- Make sure you have `zip` and `fpm`:

```
sudo apt-get install zip
sudo apt-get install ruby-dev gcc
sudo gem install fpm
```

You also must have the `aws cli` tools installed and configured on the
machine you're deploying from.

The rough guide to deployment is as follows:

- Get your changes merged into `master`, ensuring they've passed tests and everything.

- Deploy the `master` branch onto our `staging` environment, and make
  sure the deploy goes smoothly. In the future, this is a place to run
  integration/QA tests.

- Deploy into the `production` environment.

It's strongly advised you deploy into staging first.

*VERY IMPORTANT:* Running a deployment does not run database
migrations.  You need to run these yourself (see below).

Adding `proxy` makes sure that you're using fwdproxy for any outbound
SSH connections. You only need to use the proxy when there are
outgoing SSH connections involved, like when you're doing a
migration. It's not needed for just deploying code.

Production
----------

To make a production deployment, run `fab prod deploy`. You must be on
the `master` branch to do a production deployment. This will show
deployment progress during deployment, and you can also track
deployment status on the AWS console.


Staging
-------

You can also deploy into staging: `fab staging deploy`. This is
intentionally very similar to deploying into production.

A staging environment is a production environment, but it's hooked up
to a different load balancer and is accessible at
[staging.example.com](https://staging.example.com).

Treat the staging database as disposable. You can destroy this DB and
re-create it with `fab refresh_staging_db`. It's wise to run this
before a deployment that contains a migration so you can test against
something very close to the current production DB.

Migrations
----------

We now use django's builtin migration system (we formerly used South).

The workflow is straightforward:

    # edit your models
    vi models.py

    # create the migration file
    python manage.py makemigrations

*Note! You gotta commit the migration files.*
These are a critical part of the application.

Running a migration in local development is simple. Just run `python manage.py migrate endagaweb` to apply the migrations to your development database.

For the `staging` or `production` environment, use `fab proxy <environment> migrate`. This is equivalent to `python manage.py migrate --noinput`.

Under the covers, this:

- Sets up all outgoing ssh connections to use fwdproxy.

- Connects to a machine in the environment you specified (randomly
  picked out of all the machines w/ the proper environment tags).

- Runs the migration with the *currently installed* version of the
  application, and the environment settings already on that machine.
  So you'll want to do a deployment first.  You could run `fab prod
  deploy migrate`, which would do everything one go.

To run a migration against a specific application, run:

`fab proxy <environment> migrate:authtoken`,

which is equivalent to `python manage.py migrate authtoken`.

Similarly, to specify a particular migration number (e.g., to perform
a rollback),

run `fab proxy <environment> migrate:endagaweb,0010`

which is equivalent to `python manage.py migrate endagaweb 0010`.

Django Admin
============

Our admin site is at `/django-admin`. To access this, you'll need to
be a superuser or to create one afresh:

```
python manage.py createsuperuser
```

When connected to staff.example.com, you can "ghost" user accounts
(i.e., log in as that user), assuming you've logged in with your
example.com account and have been given permissions to do so. To log in
as a user, navigate to their user page in django-admin, and click the
"log in as user" button in the top right corner.


Sending Data to a BTS
=====================

We use checkin responses to communicate:
 * network config data
 * billing tier info
 * (see endagaweb.models.BTS.checkin for more)

We use async post to directly send:
 * credit adjustments
 * SMS to a user


Client metapackage autoupgrades
===============================

The webapp exposes some controls for autoupgrading client boxes. When
new software is pushed to a channel on repo.endaga, someone, via
django-admin, should add a `models.ClientRelease` for the
corresponding metapackage release to `beta` or `stable`.


Resetting the test DB
=====================

If the test db needs to be rebuilt, login to the `db` VM:

    $ vagrant ssh db
    vagrant@vagrant-ubuntu-trusty-64:~$ sudo -u postgres psql
    postgres=# drop database endagaweb_dev;
    postgres=# create database endagaweb_dev;
