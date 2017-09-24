from htmlemailer import send_mail

from models import *

from datetime import datetime, timedelta

from django.conf import settings

def send_email_verification(email, searchkey, action, send_email=True):
	r = Record()
	r.email = email
	r.set_code()
	r.searchkey = searchkey
	r.set_action(action)
	
	if send_email:
		send_record_email(email, action, r)
		
	r.save()

	return r
	
def send_record_email(email, action, r):
		return_url = r.url()
		kill_url = r.killurl()
	
		fromaddr = getattr(settings, 'EMAILVERIFICATION_FROMADDR',
				getattr(settings, 'SERVER_EMAIL', 'no.reply@example.com'))
		if hasattr(action, "email_from_address"):
			fromaddr = action.email_from_address()

		ctx = {
			"return_url": return_url,
			"kill_url": kill_url,
		}

		if hasattr(action, 'email_template_context'):
			ctx.update(action.email_template_context())
			
		send_mail(action.email_template, fromaddr, [email], ctx, fail_silently=False)
	
def resend_verifications(test=True):
	# Build up a union of queries, one for each number of retries made so
	# far, starting with zero. Each level has a different delay time since the
	# last send.
	search = None
	for retries in xrange(len(RETRY_DELAYS)):
		q = Record.objects.filter(
			retries = retries,
			hits = 0,
			killed = False,
			created__gt = datetime.now() - timedelta(days=EXPIRATION_DAYS),
			last_send__lt = datetime.now() - RETRY_DELAYS[retries]
			)
		if search == None:
			search = q
		else:
			search |= q

	for rec in search:

		try:
			action = rec.get_action()
		except:
			continue
		
		if not hasattr(action, "email_should_resend"):
			continue
		if not action.email_should_resend():
			continue
			
		print rec.retries, rec.created, rec.last_send, rec,
		if test:
			print "test"
			continue
		else:
			print
		
		try:
			send_record_email(rec.email, action, rec)
		except Exception as e:
			print "\tfailed:", e
			continue
			
		rec.retries += 1
		rec.last_send = datetime.now()
		rec.save()

def clear_expired():
	return Record.objects.filter(created__lt = datetime.now() - timedelta(days=EXPIRATION_DAYS)).delete()
