Osmocom VTTY python client, which allows reading network and bts state,
and writing configuration. Also provides access to the HLR allowing to
create new subscribers, update existing subscribers, reading camped
subscribers, and sending sms.

Designed to be extensible with support for other Osmocom VTTY functionality.
Writing a new module is a matter of writing a few lines of regex and setter
methods in the correct context.

### requirements
* OpenBSC master branch (tested with `cdc548c`)

### installation
```shell
$ python setup.py install
```

### usage
The interface is designed to be used as a context manager. This feels most
natural given the state machine permission system you need to navigate to
perform different operations. The context manager will handle exiting the
default permission state and closing the socket for you, even in the case
of general exceptions.

```python
import osmocom

with osmocom.network.Network() as n:
    print n.show()
    n.set_mcc(901)

with osmocom.bts.BTS() as b:
    print b.show(0) # bts with ID 0
    b.set_band(0, 'DCS1800')

with osmocom.subscribers.Subscribers() as s:
    s.create('901550000000000')
    print s.show('901550000000000')
    print s.show('IMSI901550000000000') # the prefix IMSI is ignored

```

### releases
* 0.0.1 - basic utilities for managing the network, bts and subscribers
* 0.1.0 - Add GSUP server

### development
Changes to the subscriber data protobuf need to be regenerated. A Makefile is
included in osmoocom/gsup/store/protos for this purpose. Run `sudo make` to install
dependencies and generate the protobuf code.

### testing
To run the `nose` tests run:

```shell
$ nosetests
```

To run the integaration tests, run:
```shell
$ python test.py
```

### known issues
* creating a subscriber that already exists causes osmo-nitb to segfault
on x86 builds.
* deleting a subscriber doesn't really work though it returns successfully
