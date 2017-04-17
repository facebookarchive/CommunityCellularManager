i18n/l10n support for Community Cellular Manager
------------------------------------------------

This package contains translation files for Community Cellular Manager
(CCM). We use gettext.

In general, user-facing strings in Python code should use the following convention:

    import gettext
    from libendaga.config import ConfigDB
    cdb = ConfigDB()
    gt = gettext.translation("endaga", cdb['localedir'], [cdb['locale'], "en"]).gettext
    gt("Your message has been delivered to %(from)s") % {'from': from_}

A couple things to note here. First, we don't use an underscore to prefix gettext strings,
we use gt(); this is because _ is used as a temp variable in many scripts (TODO: fix this :-] ).

To use in a Freeswitch config, use as follows:

    <action application="python" data='endaga_i18n Your number is %(number)s|{"number": ${vbts_callerid}}'/>
    <action application="python" data="VBTS_Send_SMS ${vbts_callerid}|${vbts_tp_dest_address}|${_localstr}"/>

Two things to note in this example. The output of `endaga_18n` stores
the translated string in the `${_localstr}` variable.
Secondly, Freeswitch escapes strings weirdly.
So, to pass a dictionary of variables to `endaga_i18n`,
the variable names in the dictionary must be double quoted.
If they're single quoted, FS seems to strip the quotes out
before passing the arguments to `mod_python`.

We use a couple fabric commands to manage our translations:

- `extract_pot`: Extract the translatable strings from the whole project, and put them into endaga-lang.
  Run this command to generate the PO template file that contains all the strings from the entire project.
  Note, this file doesn't need to be tracked in git.
- `compile_lang`: Update the .mo and .po files in the locales.
  Once you have a .POT file generated, this command generates all the .po and compiled .mo files for each language.
  If a .po file already exists for a locale, we update it; otherwise, we create a new one.
  The .po files should be tracked in the repo; we do not need to track the .mo files.

TO add a new language, add the locale id in the list of locales in the fabfile,
then run `fab dev compile_lang`. This will generate the .po file, and you can then translate that.

Here are old notes used in development (Dec 17, 2014),
saved for historical purposes and understanding why certain decisions were made:

Before we added i18n support:
- Strings are *hardcoded* in twilio-sms-server for registration, delivery receipts
- Strings are in the configDB for billing
- Voice recordings are... nonexistent,
  but hardcoded in as flite tts in the freeswitch confs (just the no money message)
- Strings hardcoded in dialplan/chatplans:
    - `dialplan/10_credit_check`
    - `dialplan/11_number_check`
    - `dialplan/25_no_money`
    - `chatplan/01_provisioning`
    - `chatplan/02_unprovisioned`
    - `chatplan/12_credit_check`
    - `chatplan/13_number_check`
    - `chatplan/20_error`
    - `chatplan/22_no_money`
    - `chatplan/99_invalid`

Goal: Ship "language packs" with image that are used in place of these strings.
- Include language packs as their own package (endaga-lang), access via gettext
- Expose an HTTP interface to pull various strings (i.e., to get this from the FS confs)
    - As far as I can tell, no good way to keep i18n in FS without leaking
      application logic elsewhere.
    - We access w/ a python script, `endaga_i18n.py`, inside FS dialplan/chatplan

Generating i18n and l10n files
- Use python-babel.
- Process for translating and stuff: (http://www.supernifty.org/blog/2011/09/16/python-localization-made-easy/)
    1) Extract strings from source code:

            pybabel extract . -k gt > data/POT/libendaga.pot
            # 'libendaga' is arbitrary, this is just the domain. Can be whatever.

       This creates a .PO template file, that can then be handed off to various
       translators to get language-specific .po files back. Call these files
       you get back libendaga_<lang>.po.

    2) Generate the .PO files:

            pybabel init -l en -i libendaga.en.po -d ./locale

       This will create the locale directory structure, and put the .po files
       in the right place according to the language specified.

    3) Generate the .MO files. These are what are actually used to do the
       dynamic translation -- some binary scheme.

            pybabel compile -d locale -f

       Once you have these, you should be able to put the entire locale
       directory structure somewhere well-known, and point your programs to it.
       They will then pick up the proper translations, assuming some exist.

    4) Actually use the translations. Put the following at the top of your scripts:

            import gettext
            gt = gettext.translation("endaga", "/path/to/localedir", ["es", "en"]).gettext

       Then, you can wrap any string with gt(...) and you'll get the
       translation. What we'll probably want to do for setting locale
       dynamically is put our "preferred" language first in the list, but
       always include en_US as the second language, and always ship that locale
       pack. That way, we'll have something to display in all cases.
