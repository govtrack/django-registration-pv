from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import render

import datetime

from models import *

def processcode(request, code):
	try:
		rec = Record.objects.get(code=code)
	except:
		return render(request, 'emailverification/badcode.html', { "code": code })

	if rec.is_expired():
		return render(request, 'emailverification/expired.html')

	rec.hits += 1
	rec.save() # save early in case view raises an exception

	axn = rec.get_action()
		
	ret = axn.get_response(request, rec)
		
	rec.set_action(axn)
	rec.save()
		
	return ret
	
def killcode(request, code):
	try:
		rec = Record.objects.get(code=code)
	except:
		return render(request, 'emailverification/badcode.html', { "code": code })

	rec.killed = True
	rec.save()

	return render(request, 'emailverification/codekilled.html', { "code": code })

def emailping(request, code):
	try:
		ping = Ping.objects.get(key=code)
		ping.pingtime = datetime.datetime.now()
		ping.save()
	except Ping.DoesNotExist:
		pass

	# This should be the smallest possible transparent PNG.
	return HttpResponse('\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
		content_type="image/png")
	
