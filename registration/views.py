from django import forms
from django.http import HttpResponseNotFound, HttpResponseRedirect, HttpResponse
from django.urls import reverse, resolve
from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.backends import ModelBackend
from django.contrib import messages
from django.contrib.auth.decorators import login_required

import urllib.parse, random

from emailverification.utils import send_email_verification

from . import providers
from .models import *
from .helpers import validate_username, validate_password, validate_email
from .helpers import json_response, validation_error_message

from django.conf import settings

def loginform(request):
	errors = ""
	
	if "email" in request.POST and "password" in request.POST:
		email = None
		try:
			email = forms.EmailField().clean(request.POST["email"])
		except forms.ValidationError as e:
			errors = "That's not a valid email address."
			
		password = None
		try:
			password = forms.CharField().clean(request.POST["password"])
		except forms.ValidationError as e:
			#print e
			pass
	
		if email != None and password != None:
			user = authenticate(request, email=email, password=password)
			if user is not None:
				if not user.is_active:
					errors = "Your account has been disabled!"
				elif user.is_staff or user.is_superuser: # the email/password backend already checked this
					errors = "Staff cannot log in this way."
				else:
					login(request, user)
					if request.POST.get("next","").strip() != "":
						try:
							validate_next(request, request.POST["next"]) # raises exception on error
							return HttpResponseRedirect(request.POST["next"])
						except Exception as e:
							#print e
							pass # fall through
					return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
			else:
				errors = "Your email and password were incorrect."
		    
	return render(request, 'registration/login.html', {
		"errors": errors,
		"email": "" if not "email" in request.POST else request.POST["email"],
		"password": "" if not "password" in request.POST else request.POST["password"],
		"next": request.GET.get("next", request.POST.get("next", "")),
		})

def logoutview(request):
	if request.user.is_authenticated:
		logout(request)

	try:
		validate_next(request, request.GET["next"]) # raises exception on error
		return HttpResponseRedirect(request.GET["next"])
	except Exception as e:
		pass # fall through

	return render(request, 'registration/loggedout.html', {})

class EmailPasswordLoginBackend(ModelBackend):
	"""
	Allows us to log users in with an email address instead of a username.
	
	This backend is registered with Django automatically by __init__.py.
	Staff login is not permitted this way so that it can be customized
	elsewhere, e.g. to add an OTP requirement.
	"""
	supports_object_permissions = False
	supports_anonymous_user = False

	def authenticate(self, request, email=None, password=None):
		try:
			user = User.objects.get(email=email)
			if user.is_staff or user.is_superuser:
				return None # admin login required
			if user.check_password(password):
				return user
		except:
			pass
		return None

def validate_next(request, next):
	# We must not allow anyone to use the redirection that occurs in logins
	# to create an open redirector to spoof URLs.
	
	# The easiest thing to do would be to only allow local URLs to be redirected
	# to, however if we're operating in an iframe then we may want to open
	# a OAuth lijnk a link with target=_top (otherwise Chrome loses the referer
	# header which happens to be important to me) and a next= that is off
	# our domain but to a page that will re-load the widget. Sooooo... we'll allow
	# unrestricted next= if the referer is on our domain. (nb. <base target="_top"/>)
	try:
		if urllib.parse.urlparse(request.META.get("HTTP_REFERER", "http://www.example.org/")).hostname == urllib.parse.urlparse(settings.SITE_ROOT_URL).hostname:
			return
	except: # invalid referrer header
		pass

	# Check that the page is a local page by running it through URLConf's reverse.
	
	if "#" in next: # chop off fragment
		next = next[0:next.index("#")]
	if "?" in next: # chop off query string
		next = next[0:next.index("?")]
	if next[0:len(settings.SITE_ROOT_URL)] == settings.SITE_ROOT_URL:
		next = next[len(settings.SITE_ROOT_URL):]
	func, args, kwargs = resolve(next) # validate that it's on our site. raises a Http404, though maybe wrapping it in a 403 would be better
	
def external_start(request, login_associate, provider):
	if 'googlebot(at)googlebot.com' in request.META.get('HTTP_FROM', ''):
		return HttpResponseNotFound()
	
	if not provider in providers.providers:
		return HttpResponseNotFound()

	if login_associate == "associate" and not request.user.is_authenticated:
		login_associate = "login"

	if login_associate == "verify":
		request.session["registration_external_verify"] = None

	if "next" in request.GET:
		validate_next(request, request.GET["next"]) # raises exception on error
		request.session["oauth_finish_next"] = request.GET["next"]
		
	if providers.providers[provider]["method"] == "openid2":
		# the callback must match the realm, which is always SITE_ROOT_URL
		callback = settings.SITE_ROOT_URL + reverse(external_return, args=[login_associate, provider])
	else:
		# be nicer and build the callback URL from the HttpRequest, in case we are not
		# hosting SITE_ROOT_URL (i.e. debugging).
		callback = request.build_absolute_uri(reverse(external_return, args=[login_associate, provider]))
	request.session["oauth_finish_url"] = callback

	scope = request.GET.get("scope", None)
	mode = request.GET.get("mode", None)

	try:
		redirect_url = providers.methods[providers.providers[provider]["method"]]["get_redirect"](request, provider, callback, scope, mode)
	except Exception as e:
		return HttpResponse("There was a problem beginning the login process: " + str(e))
	response = HttpResponseRedirect(redirect_url)
	response['Cache-Control'] = 'no-store'
	return response
		
def external_return(request, login_associate, provider):
	try:
		finish_authentication = providers.methods[providers.providers[provider]["method"]]["finish_authentication"]
		
		(provider, auth_token, profile) = finish_authentication(
			request,
			provider,
			request.session["oauth_finish_url"]
			)
		del request.session["oauth_finish_url"]
	except providers.UserCancelledAuthentication:
		request.goal = { "goal": "oauth-cancel" }
		return HttpResponseRedirect(request.session["oauth_finish_next"] if "oauth_finish_next" in request.session else reverse(loginform))
	except Exception as e:
		# Error might indicate a protocol error or else the user denied the
		# authorization. If finish_authentication returns None, a TypeError
		# is raised in trying to assign it to the tuple above.
		import sys
		sys.stderr.write("oauth-fail: " + str(e) + "\n");
		request.goal = { "goal": "oauth-fail" }
		messages.error(request, "There was an error logging in.")
		return HttpResponseRedirect(request.session["oauth_finish_next"] if "oauth_finish_next" in request.session else reverse(loginform))

	# The provider specifies a persistent user ID.
	uid = providers.providers[provider]["profile_uid"](profile)

	# On "verify" actions, just put the account info in the session and
	# redirect to the next page.
	if login_associate == "verify":
		request.session["registration_external_verify"] = {
			"provider": provider,
			"auth_token": auth_token,
			"profile": profile,
			"uid": uid,
		}
		return HttpResponseRedirect(request.session["oauth_finish_next"] if "oauth_finish_next" in request.session else reverse(loginform))

	# The provider may request that on new accounts we migrate from an old
	# provider/uid pair.
	migrate_from = providers.providers[provider].get("migrate_from", lambda p : None)(profile)
	if migrate_from:
		try:
			migrate_from = AuthRecord.objects.get(provider=migrate_from[0], uid=migrate_from[1])
		except:
			migrate_from = None
	
	# be sure to get this before possibly logging the user out, which clears session state
	next = settings.LOGIN_REDIRECT_URL
	if "oauth_finish_next" in request.session:
		next = request.session["oauth_finish_next"]
	
	rr = AuthRecord.objects.filter(provider = provider, uid = uid)
	if len(rr) == 0:
		# These credentials are new to us.
		
		# If we are doing an association to an existing account, take care of it
		# now and redirect.
		user = None
		if login_associate == "associate" and request.user.is_authenticated:
			user = request.user
			request.goal = { "goal": "oauth-associate" }

		# If we are migrating from an old id scheme, we have loaded an old AuthRecord.
		# Copy the user from that.
		elif migrate_from:
			user = migrate_from.user
			
		# If the profile provides a trusted email address which is tied to a
		# registered account here, then we can log them in and create
		# a new AuthRecord.
		elif "trust_email" in providers.providers[provider] and providers.providers[provider]["trust_email"] and "email" in profile:
			try:
				user = User.objects.get(email = profile["email"])
				request.goal = { "goal": "oauth-login" }
			except:
				pass
			
		if user != None:
			rec = AuthRecord()
			rec.provider = provider
			rec.uid = uid
			rec.user = user
			rec.auth_token = auth_token
			rec.profile = profile
			rec.save()
			
			# new AuthRecord for existing account --- log the user in, but not staff because that requires an admin login (see elsewhere)
			if user != request.user and not user.is_staff and not user.is_superuser:
				if request.user.is_authenticated: # avoid clearing session state
					logout(request)
				user = authenticate(user_object = user)
				login(request, user)
			
			return HttpResponseRedirect(next)
			
		# Otherwise log the user out so we can do a new user registration.
		if request.user.is_authenticated:
			logout(request)
		
		# This is a third-party login that causes a new user registration. We need
		# to let the user choose a username and if the login provider does not
		# provide a trusted email address, then we have to ask for an email address
		# and check it. We'll store what we know in the session state for now.
		# Don't set a goal here since we'll set the registration goal when it's complete.
		request.session["registration_credentials"] = (provider, auth_token, profile, uid, next)
		return HttpResponseRedirect(reverse(external_finish))
	
	# Credentials exist.
	
	rr = rr[0]
	
	# update latest profile information
	rr.auth_token = auth_token
	rr.profile = profile
	rr.save()
	
	# If we are doing an association....
	if login_associate == "associate" and request.user.is_authenticated:
		request.goal = { "goal": "oauth-associate" }
		
		if rr.user != request.user:
			# if the record is associated with an inactive account allow
			# the credentials to be poached
			if not rr.user.is_active:
				rr.user = request.user
				rr.save()
				messages.info(request, "You have connected your " +  providers.providers[provider]["displayname"] + " account.")
				
			# But if it's associated with a different active user, we can't change
			# the association.
			else:
				messages.info(request, "Your " +  providers.providers[provider]["displayname"] + " account is already connected to a different account here. It cannot be connected to a second account.")
				
		## We already have made this association.
		### BUT WE MIGHT BE ADDING SCOPE.
		#else:
		#	messages.info(request, "You already are connected to a " +  providers.providers[provider]["displayname"] + " account. To connect to a different account, you may need to log out from the " +  providers.providers[provider]["displayname"] + " website first.")
		
	# We are logging the user in.
	else:
		# If the user is not logged in or the record is associated with a different user,
		# switch the login to that user. Otherwise, the user is already logged in with
		# that account so there is nothing to do.
		request.goal = { "goal": "oauth-login" }
		if not request.user.is_authenticated or (request.user.is_authenticated and request.user != rr.user):
			if not rr.user.is_active:
				# Can't log in an inactive user.
				messages.error(request, "Your account is disabled.")
				return HttpResponseRedirect(reverse(loginform))
			if rr.user.is_staff or rr.user.is_superuser:
				# Can't log in staff -- see elsewhere.
				messages.error(request, "Staff accounts cannot log in this way.")
				return HttpResponseRedirect(reverse(loginform))
				
			if request.user.is_authenticated:
				# The auth record points to a different user, so log the user out and
				# then log them back in as the other user.
				prev_username = request.user.username
				logout(request)
				messages.warning(request, "You have been logged out of the " + prev_username + " account and logged into the account named " + rr.user.username + ".")
			
			user = authenticate(user_object = rr.user)
			login(request, user)
		
	return HttpResponseRedirect(next)

def external_finish(request):
	if not "registration_credentials" in request.session:
		# User is coming back to this page later on for no good reason?
		if request.user.is_authenticated:
			return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
		else:
			return HttpResponseRedirect("/")
	
	# Recover session info.
	(provider, auth_token, profile, uid, next) = request.session["registration_credentials"]

	# Set information for later.
	axn = RegisterUserAction()
	axn.provider = provider
	axn.uid = uid
	axn.auth_token = auth_token
	axn.profile = profile
	axn.next = next
	
	return registration_utility(request, provider, profile, axn)
	
def new_user(request):
	axn = RegisterUserAction()
	axn.next = request.POST.get("next", "/accounts/profile")
	return registration_utility(request, None, {}, axn)
		
def registration_utility(request, provider, profile, axn):
	username = None
	if "username" in request.POST:
		username = request.POST["username"]
	else:
		# Guess a username.
		if "screen_name" in profile:
			username = profile["screen_name"]
		elif "email" in profile and "@" in profile["email"]:
			username = profile["email"][0:profile["email"].index("@")]
		elif "email" in request.POST and "@" in request.POST["email"]:
			username = request.POST["email"][0:request.POST["email"].index("@")]

	email = None
	if "email" in request.POST:
		email = request.POST["email"]
	elif "email" in profile and len(profile["email"]) <= 64:
		# Pre-populate an email address.
		email = profile["email"]

	# Validation
		
	errors = { }
	
	if username:
		try:
			username = validate_username(username)
		except Exception as e:
			if settings.REGISTRATION_ASK_USERNAME:
				errors["username"] = validation_error_message(e)
			else:
				# make up a username that validates (i.e. not already taken)
				c = User.objects.count() + 100
				while True:
					try:
						username = validate_username("Anonymous" + str(random.randint(c, c*5)))
						break
					except:
						continue
	elif request.method == "POST" and settings.REGISTRATION_ASK_USERNAME:
		errors["username"] = "Provide a user name."
	
	if email:
		try:
			email = validate_email(email)
		except Exception as e:
			errors["email"] = validation_error_message(e)
	elif request.method == "POST":
		errors["email"] = "Provide an email address."

	password = None
	if not provider:
		if request.method == "POST":
			try:
				password = validate_password(request.POST.get("password", ""))
			except Exception as e:
				errors["password"] = validation_error_message(e)

	if len(errors) > 0 or request.method != "POST":
		# Show the form again with the last entered field values and the
		# validation error message.
		return render(request, 'registration/register.html',
			{
				"provider": provider,
				"username": username,
				"ask_username": settings.REGISTRATION_ASK_USERNAME,
				"email": email,
				"errors": errors,
				"site_name": settings.APP_NICE_SHORT_NAME,
			})
	
	# Beign creating the account.
	
	axn.username = username
	axn.email = email
	axn.password = password
	
	# If we trust the email address --- because we trust the provider --- we can
	# create the account immediately.
	if provider and "trust_email" in providers.providers[provider] and providers.providers[provider]["trust_email"] and "email" in profile and email == profile["email"]:
		return axn.finish(request)
		
	# Check that the email address is valid by sending an email and delaying registration.

	request.goal = { "goal": "register-emailcheck" }
	
	send_email_verification(email, None, axn)
	
	return render(request, 'registration/registration_check_inbox.html', {
		"email": email,
		"site_name": settings.APP_NICE_SHORT_NAME,
		})

class RegisterUserAction:
	username = None
	email = None
	password = None
	provider = None
	uid = None
	auth_token = None
	profile = None
	next = None
	
	def __unicode__(self):
		return "RegisterUser(%s,%s,%s)" % (self.username, self.email, (self.provider + ":" + str(self.uid)) if self.provider else "direct")
	
	def get_response(self, request, vrec):
		return self.finish(request)
		
	def email_should_resend(self):
		return not User.objects.filter(email=self.email).exists()
		
	def finish(self, request):
		try:
			del request.session["registration_credentials"]
		except:
			pass

		try:
			# If this user has already been created, just log the user in.
			user = authenticate(user_object = User.objects.get(email=self.email))
			if user.is_staff or user.is_superuser:
				# Can't log in staff.
				messages.error(request, "Staff accounts cannot log in this way.")
				return HttpResponseRedirect(reverse(loginform))
			login(request, user)
			return HttpResponseRedirect(self.next)
		except:
			pass
		
		user = User.objects.create(username=self.username, email=self.email)
		if not self.password:
			user.set_unusable_password()
		else:
			user.set_password(self.password)
		user.save()
				
		user = authenticate(user_object = user)
		login(request, user)
	
		if self.provider:
			rec = AuthRecord()
			rec.provider = self.provider
			rec.uid = self.uid
			rec.user = user
			rec.auth_token = self.auth_token
			rec.profile = self.profile
			rec.save()		
			request.goal = { "goal": "register-oauth" }
		else:
			request.goal = { "goal": "register-simple" }
		
		return HttpResponseRedirect(self.next)
		
	@property
	def email_template(self): return "registration/email/register"
	def email_template_context(self): return { "site": settings.APP_NICE_SHORT_NAME }

class DirectLoginBackend(ModelBackend):
	"""
	Allows us to log users in without knowing the user's password
	from Python code, using authenticate(user_object = user). But
	if the user.is_active is False, then authentication fails!
	
	This backend is registered with Django automatically by __init__.py.
	"""
	supports_object_permissions = False
	supports_anonymous_user = False

	def authenticate(self, request, user_object=None):
		if not user_object.is_active:
			return None
		return user_object

@json_response
def ajax_login(request):
	email = validate_email(request.POST["email"], for_login=True)
	password = validate_password(request.POST["password"])
	user = authenticate(email=email, password=password)
	if user == None:
		sso = AuthRecord.objects.filter(user__email=email)
		if len(sso) >= 1: # could also be the password is wrong
			return { "status": "fail", "msg": "You use an identity service provider to log in. Click the %s log in button to sign into this site." % " or ".join(set([providers.providers[p.provider]["displayname"] for p in sso])) }
		return { "status": "fail", "msg": "That's not a username and password combination we have on file." }
	elif not user.is_active:
		return { "status": "fail", "msg": "Your account has been disabled." }
	elif user.is_staff or user.is_superuser: # the email/password backend already checked this
		return { "status": "fail", "msg": "Staff cannot log in this way." }
	else:
		login(request, user)
		return { "status": "success" }
		
class ResetPasswordAction:
	userid = None
	email = None
	def get_response(self, request, vrec):
		# Log the user in.
		user = User.objects.get(id = self.userid, email = self.email)
		user = authenticate(user_object = user)
		if not user: # User.is_active is False
			messages.warning(request, "Your account has been disabled.")
			return HttpResponseRedirect("/")
		if user.is_staff or user.is_superuser:
			messages.warning(request, "Staff cannot log in this way.")
			return HttpResponseRedirect("/accounts/profile")
		login(request, user)
		
		# Tell them what to do.
		messages.warning(request, "You have been logged into your account. Please now set a password in the form below.")
		return HttpResponseRedirect("/accounts/profile")
		
	@property
	def email_template(self): return "registration/email/reset_password"
	def email_template_context(self): return { "site": settings.APP_NICE_SHORT_NAME }

def resetpassword(request):
	status = ""
	if request.POST.get("email", "").strip() != "":
		# Valid reCAPTCHA.
		import urllib.request, urllib.parse, urllib.error, json
		ret = json.loads(urllib.request.urlopen(
			"https://www.google.com/recaptcha/api/siteverify",
			data=urllib.parse.urlencode({
				"secret": settings.RECAPTCHA_SECRET_KEY,
				"response": request.POST.get("g-recaptcha-response", ""),
				"remoteip": request.META['REMOTE_ADDR'],
			}).encode("utf8")).read().decode("utf8"))
		
		if not ret.get("success"):
			status = "; ".join(ret.get("error-codes", [])) + ". If you can't past this point, please contact us using the contact link at the bottom of this page."

		else:
			try:
				user = User.objects.get(email = request.POST["email"].strip())
				
				axn = ResetPasswordAction()
				axn.userid = user.id
				axn.email = user.email 
				
				send_email_verification(user.email, None, axn)
			except:
				pass
		
			status = "We've sent an email to that address with further instructions. If you do not receive an email, 1) check your junk mail folder and 2) make sure you correctly entered the address that you registered on this site."
			
	return render(request, 'registration/reset_password.html', {
		"status": status,
		"RECAPTCHA_SITE_KEY": settings.RECAPTCHA_SITE_KEY,
		})

@login_required
def profile(request):
	errors = { }
	success = []
	
	if request.method == "POST":
		email = None
		if request.POST.get("email", "").strip() != "":
			try:
				email = validate_email(request.POST.get("email", ""), skip_if_this_user=request.user)
			except Exception as e:
				errors["email"] = validation_error_message(e)
	
		password = None
		if request.POST.get("password", "").strip() != "":
			try:
				password = validate_password(request.POST.get("password", ""))
			except Exception as e:
				errors["password"] = validation_error_message(e)

		username = None
		if settings.REGISTRATION_ASK_USERNAME:
			if request.POST.get("username", "").strip() != request.user.username:
				try:
					username = validate_username(request.POST.get("username", ""))
				except Exception as e:
					errors["username"] = validation_error_message(e)

		if len(errors) == 0:
			if username or password or email:
				u = request.user
				if password:
					u.set_password(password)
					success.append("Your password was updated.")
				if username:
					u.username = username
					success.append("Your user name was updated.")
				if email and email.lower() == u.email.lower():
					# Maybe the case is being changed. Or nothing is being changed.
					if email != u.email:
						success.append("Your email address was updated.")
					u.email = email
					email = None # don't send a confirmation email
				u.save()
				
			if email:
				axn = ChangeEmailAction()
				axn.userid = request.user.id
				axn.email = email
				send_email_verification(email, None, axn)

				return render(request, 'registration/registration_check_inbox.html', {
					"email": email,
					"site_name": settings.APP_NICE_SHORT_NAME,
					})

	return render(request, 'registration/profile.html', {
		"site_name": settings.APP_NICE_SHORT_NAME,
		"ask_username": settings.REGISTRATION_ASK_USERNAME,
		"sso": request.user.singlesignon.all(),
		"errors": errors,
		"success": " ".join(success) if len(success) > 0 else None,
		})

class ChangeEmailAction:
	userid = None
	email = None
	
	def __unicode__(self):
		return "ChangeEmail(%d,%s)" % (self.userid, self.email)
		
	def email_should_resend(self):
		return not User.objects.filter(email=self.email).exists()
	
	def get_response(self, request, vrec):
		user = User.objects.get(id = self.userid)
		
		user.email = self.email
		user.save()
		
		user = authenticate(user_object = user)
		if not (user.is_staff or user.is_superuser): # can't log in staff, see elsewhere
			login(request, user)
		
		return HttpResponseRedirect("/accounts/profile")
		
	@property
	def email_template(self): return "registration/email/change_email"
	def email_template_context(self): return { "site": settings.APP_NICE_SHORT_NAME }
