a Python client for the OpenBTS NodeManager,
providing access to several components in the OpenBTS application suite:
SMQueue, SIPAuthServe, and OpenBTS itself.


### requirements
* Endaga's OpenBTS fork (tested on `3edca32`)
* Endaga's SMQueue fork (tested on `bc292b2`)
* Endaga's SIPAuthServe fork (tested on `3affcd7`)
* Endaga's NodeManager fork (tested on `fae5611`)
* Python 2.7


### installation

```shell
$ pip install openbts
```


### usage

```python
import openbts

# read a config value from SMQueue
smqueue_connection = openbts.components.SMQueue()
response = smqueue_connection.read_config('Bounce.Code')
print response.data['value']
# 101

# update an SIPAuthServe config value
sipauthserve_connection = openbts.components.SIPAuthServe()
response = sipauthserve_connection.update_config('Log.Alarms.Max', 12)
print response.code
# 204

# get realtime OpenBTS monitoring data
openbts_connection = openbts.components.OpenBTS()
response = openbts_connection.monitor()
print response.data['noiseRSSI']
# -67

# view all subscriber data
response = sipauthserve_connection.get_subscribers()
print len(response.data)
# 78

# view tmsis entries
response = openbts_connection.tmsis()
print len(response)
# 214

# create a new subscriber by name, IMSI, MSIDSN and optional ki
subscriber = ('ada', 0123, 4567, 8901)
response = sipauthserve_connection.create_subscriber(*subscriber)
print response.code
# 200
```

see additional examples in `integration_tests.py`


### releases
* 0.1.10 - appropriately handled HTTP 304 responses as "success"
* 0.1.9 - handles duplicate IMSI entries in output of `gprs list`
* 0.1.8 - fixes ZMQError when socket is put in bad state because OpenBTS is down.  Improves error reporting on CLI
* 0.1.7 - `get_load` handles gprs utilization percentages expressed in scientific notation
* 0.1.6 - new release for an internal endaga project
* 0.1.5 - adds `components.OpenBTS.get_noise`
* 0.1.4 - new release for an internal endaga project
* 0.1.3 - adds `components.OpenBTS.get_load`
* 0.1.2 - version increment required for internal endaga project
* 0.1.1 - adds support for TMSIs
* 0.1.0 - minor release!
* 0.0.18 - fixes integration tests
* 0.0.17 - sets `RCVTIME0` on zmq sockets
* 0.0.16 - adds `envoy` to `setup.py`
* 0.0.15 - get GPRS information (experimental); prefixes other ipaddr and port attributes with `openbts_`
* 0.0.14 - `get_numbers` returns an empty list instead of raising if no number is found for an IMSI
* 0.0.13 - fixes `get_subscriber` and `create_subscriber` for the latest NM
* 0.0.12 - correctly handles `caller_id` in get / update / delete operations
* 0.0.11 - `get_subscribers` returns `account_balance` info for each subscriber
* 0.0.10 - adds read and update operations on subscriber `account_balance`
* 0.0.9 - prevents `create_subscriber` from adding duplicate IMSIs
* 0.0.8 - adds `get_imsi_from_number` method
* 0.0.7 - adds some precise SubscriberRegistry methods and removes some more general ones
* 0.0.6 - fixes distribution manifest
* 0.0.5 - pypi points to Endaga fork
* 0.0.4 - expands SIPAuthServe and SR tables
* 0.0.3 - SMQueue config operations, OpenBTS monitoring, SIPAuthServe config and subscriber operations, version command for all components
* 0.0.2 - config reading and updating for the OpenBTS component
* 0.0.1 - barebones setup for pypi


### resources
* see the [OpenBTS 4.0 manual](http://openbts.org/site/wp-content/uploads/2014/07/OpenBTS-4.0-Manual.pdf)
* and the [NodeManager source](https://github.com/RangeNetworks/NodeManager) from Range


### testing
run unit tests with `nose` after installing the required modules:

```shell
$ pip install -r requirements.txt
$ nosetests openbts --with-coverage --cover-package=openbts
```

We have quite a few similar unit tests between components.
Many could be written against `openbts.core.BaseComponent`, as the components
all inherit from this single class.  But it seems better to individually
inspect the functionality of each class in `openbts.components`. Anyway,
onward..

To run the integration tests, you'll need an OpenBTS instance running on the
same machine as the testing script.  The test will modify real system
parameters, so run it with caution.  Or, better yet, run it against a system
not in production.

```shell
$ nosetests integration_tests
$ nosetests integration_tests:SIPAuthServe
$ nosetests integration_tests:SIPAuthServe.test_get_all_subscribers
```


### release process
you need a `~/.pypirc` like this:

```
[distutils]
index-servers =
  pypi

[pypi]
repository: https://pypi.python.org/pypi
username: yosemitebandit
password: mhm
```

bump the versions in `setup.py` and here in the readme, then run:

```shell
$ git tag 0.0.1 -m 'openbts-python v0.0.1'
$ git push origin master --tags
$ python setup.py sdist upload -r pypi
```
