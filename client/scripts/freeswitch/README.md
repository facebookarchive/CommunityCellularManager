Freeswitch Scripts
==================

The scripts in this directory are meant to be called from within a Freeswitch chatplan or dialplan.

Subscriber info utility scripts:
- `VBTS_Get_IP`: Get a subscriber's IP by IMSI.
- `VBTS_Get_Port`: Get a subscriber's port by IMSI.
- `VBTS_Get_CallerID`: Get a subscriber's callerid by IMSI.
- `VBTS_Get_Account_Balance`: Get a subscriber's account balance by IMSI.
- `VBTS_Get_IMSI_From_Number`: Get a subscriber's IMSI from their number.

Other scripts:
- `endaga_i18n`: Translates a string (with optional arguments) into current locale.
  Result stored in `_localstr` channel variable.
- `VBTS_Parse_SMS`: Parses an SMS and sets channel variables representing
  the exports defined in `SMS_Parse.parse()`.
- `VBTS_Send_SMS`: Sends an SMS by phone number (passes to smqueue).
- `VBTS_Send_Direct_SMS`: Sends an SMS directly to an OpenBTS instance,
  addressed by IMSI.
- `VBTS_Get_Service_Tariff`: Gets the tariff for a given service type
- `VBTS_Transfer_Credit`: Handler for credit transfer application
