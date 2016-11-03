SMS encoding and decoding utilities



### installation

```shell
$ pip install sms_utilities
```



### usage

```python

    import sms_utilities

    # Generating RDPUs:
    new_rpdu = sms_utilities.rpdu.RPDU()

    # Generating SMS-DELIVER messages:
    deliver_message = sms_utilities.SMS_Deliver.gen_msg(to, fromm, body)

    # Generating SMS-SUBMIT messages:
    submit_message = sms_utilities.SMS_Submit.gen_msg(to, body)

    # Parsing incoming SMS:
    sms_utilities.SMS_Parse.parse(rp_message)

    # Some helper methods:
    sms_utilities.SMS_Helper.to_hex2(integer)
    sms_utilities.SMS_Helper.encode_num(123)
    sms_utilities.SMS_Helper.clean('asdf')
    sms_utilities.SMS_Helper.smspdu_charstring_to_hex('bcde')
```



### license
Community Cellular Manager is BSD-licensed. We also provide an
additional patent grant. See the LICENSE and PATENTS files for more
information.



### releases
* 0.0.3 - fixes imports
* 0.0.2 - fixes MANIFEST.in filename
* 0.0.1 - initial pypi release



### testing
* nothing yet!



### reference
* PDU mode [background](http://www.gsm-modem.de/sms-pdu-mode.html)
* Wikipedia on [GSM 03.40](http://en.wikipedia.org/wiki/GSM_03.40)
* a PDF on [SMS in PDU mode](http://read.pudn.com/downloads122/doc/520173/SMS_PDU-mode.PDF)
* the [python-messaging package](https://github.com/pmarti/python-messaging)



### release process
bump the version in `setup.py`, add a note here in the readme, then run:

```shell
$ git tag 0.0.1 -m 'sms_utilities v0.0.1'
$ git push origin master --tags
$ python setup.py sdist upload -r pypi
```
