## Overview

Community Cellular Manager (CCM) is a set of programs which allow for
standalone telecom systems that can be operated by individuals or as a
network appliance inside of a traditional telecom network. The
components are as follows:

- cloud: The endagaweb Django app and other associated services
  (OpenVPN, certifier, sason) needed to manage a set of CCM clients.

- client: The software running on an OpenCellular (or similar
  hardware) access point. Manages subscribers, routing, and access
  locally while being controlled by the cloud components.

- openbts-python: A client for openbts-based systems to communicate
  with CCM-based clients.

- osmocom-python: A client for osmocom-based systems to communicate
  with CCM-based clients.

- common: Libraries shared between the client and cloud stack.

- sms_utilities: A standalone library for working with SMS PDUs.

Each subdirectory has its own README explaining the build/test/deploy
paradigm used for that particular subcomponent.

## Questions:

CommunityCellularManager@fb.com

## Join the CommunityCellularManager community

* Website: https://github.com/facebookincubator/communitycellularmanager
* Mailing list: https://groups.google.com/d/forum/community-cellular-manager

See the CONTRIBUTING file for how to help out.

## License

Community Cellular Manager is BSD-licensed. We also provide an
additional patent grant. See the LICENSE and PATENTS files for more
information.
