Community Cellular Manager (CCM) client software for the BTS.

Contains source for the `endaga` metapackage and the individual
packages `python-endaga-core`, `freeswitch-conf-endaga`, and
`endaga-lang`. The fabfile in this repo provides ways to build and
deploy all BTS-side packages.


Getting Started
===============
To get started, you should install

[Vagrant](http://www.vagrantup.com/downloads.html)

and Ansible

so you can establish a development environment.

Once you've installed vagrant, just run `vagrant up openbts` (or
osmocom if you prefer that client) and a development box will be
created based on the Vagrantfile in this repo. It will automatically
mount this directory in the VM under `/vagrant`, so you can use
whatever local development tools you like.

The development environment emulates running a full CCM BTS in a
VM, based on source you have checked out locally.  It also has all the
dependencies set up to build Freeswitch and OpenBTS if necessary.


Setup
========
After having checked out the Community Cellular Manager (CCM) repo:
- `cd` into the `client` repo
- `vagrant up osmocom` to launch the Osmocom dev VM. This will set up
all your build deps. Osmocom is suitable for most testing purposes, even
if Osmocom-compatible hardware is not available.

It is STRONGLY RECOMMENDED that the initial installation of client
software within the VM is accomplished using `apt-get` to download the
appropriate top-level package, to ensure that all dependencies are
automatically satisfied. Install `endaga-osmocom` as follows: `apt-get
install endaga-osmocom`.

To build everything from source (i.e., what you have checked out on
your box) do the following: On your box, you run `fab dev package` to
create all the `.deb` packages, then ssh into the VM (`vagrant ssh
[osmocom|openbts]`), then go to the `endaga_packages` folder and install
all of the packages (e.g., using `dpkg` or `gdebi`).

You can also call `fab dev package:package_requirements=no` to not
package up install requirements for python packages. This is useful
for development when you don't want to constantly regenerate the
requirements. Also you can run `fab dev update:flush_cache=no` to stop
the `localdev` repository from being rebuilt. This is also useful in
development workflows where just want to install a `.deb` and not
resolve dependencies.


Client Certificates
-------------------

A key component in the CCM security architecture is the VPN that
connects each client to the cloud environment. It is **ESSENTIAL**
that the client is using the same CA bundle as the certifier and VPN
servers that run in the cloud; the client registration process uses
OpenSSL to verify this and registration will fail if not. This file is
called `etage-bundle.crt`: on the client and VPN it is placed in the
`/etc/openvpn` directory, in the certifier it gets created in the
`pki` subdirectory (as `ca.crt`) and copied to the top-level
`certifier` directory (as `etage-bundle.crt`).

When installing packages from the CCM package repository the standard
'Etagecom' CA bundle will be included, and hence the installation of
that package will overwrite `/etc/openvpn/etage-bundle.crt`. In order
to support use of a local CA file, within the constraints of the
current packaging scheme, the client also checks
`etage-bundle.local.crt` when attempting to verify the client
certificate. Hence, if copying a locally generated CA bundle into the
client VM it is strongly recommended that it be copied to
`/etc/openvpn/etage-bundle.local.crt` in order to avoid subsequent
replacement by the standard packages.

Testing
-------

With the system installed, run tests to validate that it is working.

Before testing, you will also need some extra python test modules
which are managed by pip.  Pip may be broken due to a requests version
mismatch, you can fix it and install requirements via:

    $ sudo easy_install -U pip
    $ sudo pip install -r requirements.txt

And now you can run the nose test runner on the VM. Nose can root out
your tests with various degrees of granularity:

    $ cd
    $ nosetests
    $ nosetests core.tests.billing_tests
    $ nosetests core.tests.billing_tests:GetCostTest
    $ nosetests core.tests.billing_tests:GetCostTest.test_inbound_call

Beware!  The tests do things like drop the EventStore, so run these
tests on systems that are disposable.

Integration tests can also be run via `fake_phone` or `eno`. The
`fake_phone` tests require a system with freeswitch and the subscriber
registry running:

    $ nosetests fake_phone_integration_tests

They may be a bit flaky due to the order of messages being sent and
received, but two or three runs should be easily enough to get all the
tests to pass.

The `eno` tests require one or more `eno` nodes and a working BTS (see
the test module for more details). They are also run with nose:

    $ nosetests eno_integration_tests

The `eno` integration tests also interact with endaga-web APIs. For
instance, after creating a sub, a test may use an endaga-web API to
deactivate the sub as a "cleanup" step. For this to work you need an
`~/.endagarc` config file:

```yaml
test_account_api_token: 123abc
staff_api_token: 123abc
```

The `test_account_api_token` is the token of the UserProfile
associated with the BTS. The `staff_api_token` allows the tests to
release numbers.

Connecting to a development Cloud
-------

ssh into the client from the client directory ('vagrant ssh openbts'
or 'vagrant ssh osmocom' depending on the platform you chose) and get
the snowflake id 'cat /etc/snowflake'). Log into the website frontend
(192.168.10.40:8000 in your browser) and naviate to towers. Go to "add
tower" and inset that UUID. The client BTS should then register and be
show as "registered" via the interface.

Proxy client testing
-------

Client testing is supported via the 'fake_phone_client' application
shipped with client core. To use this, run the command with an
arbitrary IMSI:

'''
fake_phone_client IMSI123451234512345
'''

From here you'll see a CLI interface simulating a phone. The usage is
as follows:

'''
Usage: sms DEST CONTENT
Usage: call DEST
'''

To register for the first time, send an SMS to 101 (the registration
service) and if the BTS is correctly attached to the cloud, it will
provision you a phone number from the pool of available numbers:

'''
5065:Endaga-Fake-Phone: sms 101 test
5065:Endaga-Fake-Phone: RESPONSE: 202
Incoming SMS
To:IMSI984341234512347
From:101
Your number is 5555510184.
'''

From here, normal flows (such as calling with 'call' or SMSing other
users in the network) should work. You'll need to add credit to a
user's account via the web interface.

Radio testing
-------

Radio testing is conceptually similar to the proxy testing above. You
should be able to directly plug a radio into your box and have the
network correctly use it. If that happens, connect a test SIM (91055)
and it will be granted access to the network. 101 again provisions the
phone.

Workflow
========================
Basic workflow rules
(it's basically [github flow](http://scottchacon.com/2011/08/31/github-flow.html)):

- Master branch should always be deployable; never make changes directly to master.
- Any changes you want to make should start in their own branch
- Push your branches to Github early and often
- Once you're ready to merge into master, issue a pull request onto master via
  github. This is where code review should happen.
- Once you've passed code review, merge the pull request into master.

Expect that things in master will be pushed automatically into
production -- make sure tests pass before you push!


Development
-----------

To try to keep parity between development and deployment environments,
using our deployment scripts are part of our development workflow --
you're just shipping to your local development environment rather than
our package repo. In general, you should do your development work on
your laptop, and test your changes in a development VM (specified by
our Vagrantfile). Code that needs to compile is built on the VM.

A typical workflow would be:

- Bring up the VM: `vagrant up`, and connect to it (`vagrant ssh`). At this
  point, the VM is a blank image with no dependencies installed.
- On the VM, install the latest release from the `dev` target: `sudo apt-get
  install endaga`
- Make arbitrary changes on your laptop. Commit or don't.
- On your laptop, use our `fab` scripts to generate packages: `fab
  [GSM_ENGINE] dev package_<component>`, then install those packages with `fab dev update`./


Running a radio in the development environment
----------------------------------------------

This was tested to work under an Virtualbox 4.3.12 on an Ubuntu host.
You need to have the [Virtualbox Extension
Pack](https://www.virtualbox.org/wiki/Downloads) installed on your
machine; if you're not running the most recent Virtualbox, you will
need to get this from the [old
downloads](https://www.virtualbox.org/wiki/Download_Old_Builds)
section for your appropriate version.

After the extension pack is installed, our Vagrantfile is configured
so everything should "just work".  We do this by adding a USB filter
to our Vagrantfile that passes all RAD1's through to the client.


Deployment
==========

tl;dr: Always update version numbers, `fab dev package; fab proxy dev
shipit`, then follow the prompts.

Adding `proxy` makes sure that you're using fwdproxy for any outbound
SSH connections.

Targets
-------

Deployment of the CCM client in prod is done via Debian packages of
each of our components. Deployment logic is stored in
`commands/shipping.py` which defines a set of Fabric commands to
handle deployment.

Our package repo is at `repo.example.com`. We manage this with
[Freight](https://github.com/rcrowley/freight). The package repo has
four main branches ("distributions" in Debian terms):

- `stable`: Actual, stable, released packages. These have passed QA and should
   be installed by default on most production systems. Only packages that have
   lived on `beta` should go here.
- `beta`: Essentially pre-`stable` packages. These should have passed QA as
   well but are rolled out here before deploying on production systems. These
   are installed on select production systems.
- `test`: Packages that have not passed QA. Intended for use in-house and on
   testing deployments. Bleeding edge, but should generally work.
- `dev`: No guarantees but no restrictions for pushing packages here.
- `trusty`: A deprecated legacy target; before April 2015 this was the only
   target, and roughly corresponds to `stable`.

`stable`, `beta`, and `test` should share release version
numbers. E.g., if `v1.0.5` is released to test, that same version
number should carry all the way through stable. Major version should
get their own code branch and all releases to these repo targets
should update version numbers appropriately. This is not needed for
`dev`.

We use the same packages building scripts to generate release
packages. These are built inside the dev VM, then you ship them to the
repo server on one of the specified branches with the `shipit` fab
command. You will be prompted for what branch you want to release to.

The fab command `promote_metapackage` will move metapackage debs and
deps between distributions.  It relies on
`scripts/copy_metapackage_and_deps` -- this must be installed in
`/usr/local/bin` of repo.endaga.  There is currently no mechanism for
installing that script (or the script's deps), we just scp it over.

You can remove packages that have been pushed to the repo, but need to
be a bit careful. Packages are stored on repo.example.com in
`/var/lib/freight/apt/<release target>`, referred to by Freight as
`$VARLIB`. Any package can be removed by just deleting it with `rm`
from here. Once you've deleted it from the package library, you need
to re-build the Freight cache using `freight cache apt/<release
target>` -- this is what re-builds the Debian-structured repo that
lives in `/var/cache/freight`.

Versioning
----------

If you ship a package to a target that has the same version number as
an existing package in that target, we will skip that package (you'll
get a warning). You must *always* update the version number of a
package that you intend to ship, even if it's just the "micro" number
of the package.

Our version format in general is MAJOR.MINOR.MICRO:

- Major version number should bump when a package API changes.
- Minor version number should bump when a feature is added that doesn't break
  API.
- Micro get bumped for bugfixes and minor changes that don't affect
  functionality.

If you bump the version number of a dependency, make sure you bump the
versions of packages that depend on that (if you intend to deploy
them). So for example, if you make a small update to OpenBTS,
incrementing the micro version number, you should also update the
`endaga` metapackage's microversion number as well as its dependency
on your new release of OpenBTS.

Debugging the deployment process
--------------------------------

Sometimes you really want to ship a package with the same version
number twice (say, you're working on packaging something, and found a
bug in the packaging itself). This is possible but tricky. Log into
the repo server, and delete the relevant package file from Freight's
`$VARLIB` (`/var/lib/freight/<path_to_relevant_distro>`), then delete
the packages from `$VARCACHE` (the place the packages are actually
served, `/var/cache/freight/pool`). After that, ship your packages
(`fab dev shipit`).  This should delete all traces of the previous
package version.

If you don't do this, you'll see "size mismatch" errors when you try
to install packages. You can clear up those errors by running through
this same process.


BTS Registration
================

VPN set up with CCM:

- Users must first add their BTS's UUID to their cloud account.
- Ensure that the BTS config contains the correct registry endpoint:
  - Execute `endaga_db_get registry` and verify that the URL is a
    cloud instance accessible by the client. Note that the default, as
    set within source code, is to use a 192.168.x.x address that is
    expected to be accessible via a host-only network in the Vagrant dev
    environment.
- To change the registry endpoint, run `endaga_db_set registry
  <url>` where `<url>` specifies the API endpoint,
  e.g., https://api.etagecom.io/api/v1
  - The BTS should be able to send an untrusted registration request,
    with only its UUID, and get back a VPN conf and an API key.
  - After
    successful registration the BTS will appear as active in the web
    dashboard, and OpenVPN configuration files will be populated in
    `/etc/openvpn`.
- BTS units that are unregistered continually try to register.
  If the BTS has not been added, return a 404.
  If the BTS has been added, return VPN conf and API key.
  - Note that there is a potential attack for BTS units that have been
    added to an account, but not registered.  If an attacker sends a
    registration request with the UUID of a box in this state, they
    can potentially capture the API key for the other person.

Edge cases:

- Need to get a new cert, but you're already registered.
- Need to get a new API key (revoke the API key), but the BTS is
  already registered.
    - Solve this by putting all added BTS units in the "pending" state
      when an API key is revoked -- they'll simply re-register and get
      a new key.


Checkins
========

The BTS will periodically communicate to the cloud side, sending
UsageEvent data and, in return, receiving configuration information.
The BTS receives `config` and `events` data in the response dict.
Inside the config section, the `prices` key has a list of dictionaries
describing all outbound prefixes, the inbound Billing Tier and the
local Billing Tier.


Canonicalizing Numbers
======================

When a subscriber from Indonesia calls `9195551234` we will tack the
`ID` prefix, `62`, on to the front of the number.  We call this
process canonicalization.  This allows subs to dial local numbers
without having to include the country code.  The prefix is determined
by `number_country` which is sent in the checkin response.  To dial a
country outside of your `number_country` subscribers must include the
leading `+` sign.


Packaging
=========

After setting up an environment with ansible, you can `apt-get install
endaga` to pull the latest release of our software.  This will install
all that's required to run a client box.

The `endaga` package is created via the `package_endaga` fab command
and itself consists of several smaller packages:

```
endaga
   |- python-endaga-core
   |- python-openbts (github.com/endaga/openbts-python)
   |- freeswitch-conf-endaga
   |- endaga-lang
   |- python-freeswitch-endaga (freeswitch.org)
   |- python-sms-utilities (github.com/endaga/sms_utilities)
```

All of these packages can be built independently via various fab
commands, or all packages can be built at once with `package`.
Packaging will place debs in `~/endaga-packages` on the remote.

We use vagrant to sync VM directories and local, dev-machine repos.
For instance, if you are working on `openbts-python`, and want to
verify that `client` tests still pass, you should put the
`openbts-python` repo alongside the `client` repo on your dev
machine. Init and update submodules as necessary.  Then, in client,
package up the changes to `openbts-python` via
`package_python_openbts`.  (Note that you do not need to create a
special branch or even commit your changes.)  Then `update` will
install this new `openbts-python` deb onto the VM, and you can try the
`client` tests.


Dependencies
============

Working on a feature that needs a new library?  You will need to add
that library into an ansible playbook, `requirements.txt` or
`setup.py`, depending on how the library is used:

 * `openbts.base.yml` playbook: anything needed to install the `endaga` metapackage
 * `openbts.dev.yml` playbook: anything you need for building endaga packages
 * `requirements.txt`: libraries needed for development in the client environment and for running tests
 * `setup.py`: anything the `endaga-core` python package needs to run

Style
=====

We use the [Google Python Style
Guide](https://google-styleguide.googlecode.com/svn/trunk/pyguide.html)
to resolve ambiguity with formatting, whitespace, variable names, etc.

And we strongly recommend using `pylint` before submitting a pull
request.  It can catch things beyond style issues -- unused imports,
using `==` instead of `=`, things like that.  And there are tons of
editor plugins for emacs, vi, sublime, etc (see
[here](http://docs.pylint.org/ide-integration) for more).  Pylint will
be run in "errors-only" mode by our CI tool.

Setup and use is pretty easy, just install the package, then run
pylint against various packages with the repo's `pylintrc`.  You can
check for errors only and/or style warnings.  You can also run against
a specific module you're working on.

```
pip install -r requirements.txt
pylint --rcfile=pylintrc core
pylint --rcfile=pylintrc --errors-only core scripts
pylint --rcfile=pylintrc core/billing.py
```


History
========

In ye olden days, we had our software spread across multiple repos.
These were combined to create this one:

- interconnect-client (aka [`vbts_twilio`](https://github.com/endaga/interconnect-client))
- [`vbts_credits`](https://github.com/shaddi/vbts-credit)
- [libvbts](https://github.com/kheimerl/libvbts.git)
- [VBTS (virtual coverage)](https://github.com/kheimerl/VBTS.git)
- [Our branch of OpenBTS](https://github.com/kheimerl/openbts/tree/berkeley-power)
- [freeswitch configs](https://github.com/endaga/freeswitch-conf-endaga)
- [build script](https://github.com/endaga/build)

- Should be able to start fresh w/ a new vagrant image any time
    - Ansible or fab file should be run on local dev directory
      to deploy whatever needs to be deployed
    - By maintaining the same UUID, subscriber registry, and various endaga.conf files,
      you should be able to re-create a dev box easily.
        - Keep those files somewhere *not* in a repo.
          Maybe a particular person's dev branch?

License
=======

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional
grant of patent rights can be found in the PATENTS file in the same
directory.

This software interacts with optional third-party components that are
distributed under such licenses as Affero GPL or proprietary
commercial licenses. Please review the respective license, consult a
lawyer, or review your organization's guidelines before using and
distributing such software.
