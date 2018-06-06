from django import forms
from django.contrib.auth.models import User
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseServerError
from django import forms

import sys, json

from emailverification.utils import send_email_verification

from django.conf import settings

def validate_username(value, skip_if_this_user=None, for_login=False, fielderrors=None):
	try:
		value = forms.CharField(min_length=4 if not for_login else None, error_messages = {'min_length': "The username is too short. Usernames must be at least four characters."}).clean(value) # raises ValidationException
		if " " in value:
			raise forms.ValidationError("Usernames cannot contain spaces.")
		if "@" in value:
			raise forms.ValidationError("Usernames cannot contain the @-sign.")
			
		if not for_login:
			users = User.objects.filter(username = value)
			if len(users) > 0 and users[0] != skip_if_this_user:
				raise forms.ValidationError("The username is already taken.")
			
		return value
	except forms.ValidationError as e:
		if fielderrors == None:
			e.source_field = "username"
			raise e
		else:
			fielderrors["username"] = validation_error_message(e)
			return value
	
def validate_password(value, fielderrors=None):
	try:
		return forms.CharField(min_length=5, error_messages = {'min_length': "The password is too short. It must be at least five characters."}).clean(value)
	except forms.ValidationError as e:
		if fielderrors == None:
			e.source_field = "password"
			raise e
		else:
			fielderrors["password"] = validation_error_message(e)
			return value
		
def validate_email(value, skip_if_this_user=None, for_login=False, fielderrors=None):
	try:
		value = forms.EmailField(max_length = 75, error_messages = {'max_length': "Email addresses on this site can have at most 75 characters."}).clean(value) # Django's auth_user table has email as varchar(75)
		if not for_login:
			users = User.objects.filter(email = value)
			if len(users) > 0 and users[0] != skip_if_this_user:
				raise forms.ValidationError("If that's your email address, it looks like you're already registered. You can try logging in instead.")
		return value
	except forms.ValidationError as e:
		if fielderrors == None:
			e.source_field = "email"
			raise e
		else:
			fielderrors["email"] = validation_error_message(e)
			return value

def validation_error_message(validationerror):
	# Turns a ValidationException or a ValueError, KeyError into a string.
	if not hasattr(validationerror, "messages"):
		return str(validationerror)

	from django.utils.encoding import force_unicode
	#m = e.messages.as_text()
	m = '; '.join([force_unicode(g) for g in validationerror.messages])
	if m.strip() == "":
		m = "Invalid value."
	return m
	
def json_response(f):
	"""Turns dict output into a JSON response."""
	def g(*args, **kwargs):
		try:
			ret = f(*args, **kwargs)
			if isinstance(ret, HttpResponse):
				return ret
			ret = json.dumps(ret)
			resp = HttpResponse(ret, content_type="application/json")
			resp["Content-Length"] = len(ret)
			return resp
		except ValueError as e:
			sys.stderr.write(str(e) + "\n")
			return HttpResponse(json.dumps({ "status": "fail", "msg": str(e) }), content_type="application/json")
		except forms.ValidationError as e :
			m = validation_error_message(e)
			sys.stderr.write(str(m) + "\n")
			return HttpResponse(json.dumps({ "status": "fail", "msg": m, "field": getattr(e, "source_field", None) }), content_type="application/json")
		except Exception as e:
			if settings.DEBUG:
				import traceback
				traceback.print_exc()
			else:
				sys.stderr.write(str(e) + "\n")
				raise
			return HttpResponseServerError(json.dumps({ "status": "generic-failure", "msg": str(e) }), content_type="application/json")
	return g
	
