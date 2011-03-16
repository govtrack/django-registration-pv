Email Verification App for Django
====================

This app provides a framework for the workflow where the user
enters an email address, an email is sent to the user with a
verification code link, the user returns to the website via the link,
and then with the email address confirmed some action is taken.

This can be used for user account registration, changing email
addresses on accounts, etc. Compared to django-registration,
this module *doesn't create* the User object until the email
address is verified (this is a framework for verifying the address
before *you* create the User object).

CONFIGURATION

settings.py:

	Add "emailverification" to your Django Apps list.
	
	Optionally set:
		SITE_ROOT_URL = "http://www.example.org" # no trailing slash!
		
		    The default will be "http://%s" % Site.objects.get_current().domain.
		
		SERVER_EMAIL = "MySite <noreply@example.org>"

		    The address from which the verification codes are sent
		    The default is root@localhost.
		
		SERVER_EMAIL is used by several other aspects of Django so you can
		override the address for this project with the EMAILVERIFICATION_FROMADDR
		setting.

Add a record to your URLConf like this:

	(r'^emailverif/', include('emailverification.urls')),

The base of the URLs can be changed.
	
You will probably want to override the templates in

	templates/emailverification

by either editing them in place or copying the emailverification directory
to your site's root templates directory and editing the copies there. There
are two templates: one is for what is shown to the user when they come
with an invalid verification code (or when an error occurs unpickling the
saved state, see below), and one when the verification code has expired.
If the verification code is good, your code is called to return something
to the user.

And don't forget to run python manage.py syncdb to create the necessary
database table.

USAGE

Define a class at the *top-level* of any module which will hold onto the
information the user submitted and the email subject line and body.
It will also contain the Python code to be executed as a "callback" once
the user clicks the verification link. The class should have fields for data
stored with the instance, plus a get_response method that takes two
arguments (besides self): the HttpRequest and the emailverification.Record
object that has just been verified. Here's an example:

===================
from django.contrib.auth.models import User
from django.contrib.auth import login
...
class RegisterUserAction:
	email = None
	username = None
	password = None
	
	def email_subject(self):
		return "[subjectline of email to send user with link]"
	
	def email_body(self):
		return """Thanks for creating an account. To verify your account just follow this link:

<URL>

All the best."""
	
	def get_response(self, request, vrec):
		user = User.objects.create_user(self.username, self.email, self.password)
		user.save()
		login(request, user)
		return HttpResponseRedirect("/home#welcome")
===================

In some view in response to the user submitting a form, you'll typically
run this:

===================
from emailverification.utils import send_email_verification
...
axn = RegisterUserAction()
axn.email = email
axn.username = username
axn.password = password

send_email_verification(email, None, axn)
===================
		
And then just continue processing the view as normal, returning some
template that indicates that the user has just been sent an email. You'll
have to write that part.

send_email_verification will send the user an email with a link back to the
website and will put a random verification code into a table in the database.
The action object will be pickled (serialized) and stored alongside the
verification code in the database. When the user returns with a valid
code that hasn't expired, the action object is unpicked (deserialized) and
its get_response method is called. The default expiration time is seven
days.

The app doesn't prevent verification links from being clicked more than
once. This is by design, since a user might accidentally click on a link
twice (the first time not seeing the response). The response handler
should handle a second call as appropriate. If the callback object
changes any of its state, it will be saved back to the database so on
the second invocation it will get its saved state back. But since requests
are processed asynchronously, there is no guarantee that the state
will be saved before the second request comes in.

A note on pickling:
------------------------

Because this relies on picking, your action object *classes* must be stable
over time. If you delete the class or remove fields from it, unpickling is
going to fail and the user won't be able to continue. (A graceful message
will be displayed.) If you need to make sweeping changes, version your
classes: keep the old ones around indefinitely and add new ones. It is
safe to revise the code, however. So you can change the behavior of
the action so long as you don't change its fields too much. A good
idea might be to forget class fields and use an arbitrary dictionary of
fields, e.g.:

class RegisterUserAction:
	fields = None
	def get_response(self, request, vrec):
		user = User.objects.create_user(self.fields["username"], self.fields["email"], self.fields["password"])
		user.save()
		login(request, user)
		return HttpResponseRedirect("/home#welcome")

In this case, you don't have to worry about unpickling. Just check for the
keys in the fields property before you use them if you're not sure they
were put there in the first place. But this is a little ugly.

On the other hand, since verification codes expire after seven days, you
are free to delete old classes after that time since those pickled objects
will never be unpickled.


