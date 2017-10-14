from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from django.conf import settings

import sys

from emailverification.models import BouncedEmail

class Command(BaseCommand):
	args = ''
	help = ''
	
	def handle(self, *args, **options):
		for line in sys.stdin:
			if line.strip() == "": continue

			uid = int(line)
				
			# record the bounce
			u = User.objects.get(id=uid)
			be, is_new = BouncedEmail.objects.get_or_create(user=u)
			if not is_new:
				be.bounces += 1
				be.save()
			print u, be
