# Facebook Login

To enable Facebook social login for CCM web UI there are two
prerequisites:

1. A Facebook application for the app to authenticate with.
2. Adminstrator access to the CCM cloud UI to enable Facebook login.

Setting up Facebook login requires that the website being enabled is
accessible using a domain name, not just an IP address. That doesn't
necessarily require that a domain name be created and registered with
DNS servers, e.g., instead the domain name can be added to
`/etc/hosts` on the system from which the user is logging in. For the
purposes of this example we'll use the domain name
`ccm-web.etagecom.io`, which has been added to `/etc/hosts` as an
alias for whatever IP address the web server is reachable at.

## Creating the Facebook App

A Facebook developer can create a minimal application that enables the
use of Facebook login credentials to authenticate a user to any web
application. Follow these steps to create and configure the
application:

1. Go to http://developers.facebook.com, in the top right corner click
   on 'My Apps', 'Add a New App'. Choose a name for the application and
   select a purpose, e.g., Business.
2. Click on the new application, then on the left-hand panel click
   'Facebook Login' under 'Products'.
3. Ensure that both 'Client OAuth Login' and 'Web OAuth Login' are
   enabled on the Facebook Login Settings page.
4. In 'Valid OAuth redirect URIs' add the appropriate URI for your
   server, constructed using the template
   `http[s]://<domain-name>:<port>/accounts/facebook/login/callback`.
   If you are installing using the Vagrant 'web' VM then the protocol
   is 'http', not 'https', and the default port is 8000.

Once a Facebook app has been created and configured the cloud server
must be connected to this Facebook app.

## Connecting Cloud UI to Facebook App

Note: by default Facebook login is disabled, but can be enabled by
setting the environment variable `ENABLE_SOCIAL_LOGIN=true` prior to
starting the Django server. Use whatever method is appropriate for
your situation: it can be added to `envdir`, set on the command line,
etc.

To configure Django for Facebook login you must login as an
adminstrator ('staff' account) to the `django-admin` system. The only
mandatory step is to add the new Facebook app to 'Social
applications', at the bottom of the main settings screen:

1. Click 'Add Social Application' on the right-hand side of the
screen.
2. Set 'Facebook' as the provider, and enter whatever name you wish to
   use for display purposes (doesn't have to match what was used to
   create the app).
3. Enter the 'App ID' and 'App Secret' from the Facebook app
dashboard.
4. Associate this app with the default site: click the name of the app
   in the left-hand box, then click the right arrow to move that site
   into the 'Chosen Sites' box. By default this site is named
   'example.com', but it can be renamed at the top-level Django
   settings (although the actual name doesn't matter).
5. Click 'Save'.

Once those steps have been performed any user with a Facebook account
should be able to click 'Login using Facebook' on the main login
screen. Doing so will automatically create a new user account with
name and email derived from the user's FB profile; if the 'Mailgun'
backend has not been configured correctly the sending of a
verification email will fail, but subsequent login will succeed (and
the account can be manually verified by an administrator under the
'Users' settings).

The default settings for the system use an email domain whitelist
(`STAFF_EMAIL_DOMAIN_WHITELIST` in `endagaweb/settings/base.py`) to
restrict login to email addresses in particular domains. If a user's
Facebook profile sends an email address not included in the whitelist
the authentication attempt will fail. This can be fixed by either
changing the whitelist or unsetting the `SOCIALACCOUNT_ADAPTER`
setting.

### Enabling Facebook Login for an Existing User

It is possible, although frustratingly complicated, to enable Facebook
login for an existing user account, by making changes in various parts
of the Django settings UI:

1. In 'Social accounts', create a mapping from the existing Django
   user, e.g., 'admin', to a specific Facebook ID. Use the search
   function in the 'User' box to select the existing account, choose
   'Facebook' as the provider, and enter the associated Facebook
   ID. That ID value is app-specific and can be found by creating a
   user token using the 'Access Token Tool' on the 'Facebook for
   Developers' page, then clicking 'Debug' and getting the User ID
   value; it is NOT the same as the standard Facebook User ID. 'Extra
   data' can be left blank, but will be filled in whenever Facebook
   login is used.
2. In 'Social application tokens', use the search functions to set the
   'App' and 'Account' field to the Facebook app and the social
   account created in 1. respectively. Copy the (long) Base64 user
   access token into the 'Token' box; leave 'Token secret' empty.

Note that manually creating an association in this way does not create
an email address record for the user in the same way that having the
social account mapping be automatically created does.
