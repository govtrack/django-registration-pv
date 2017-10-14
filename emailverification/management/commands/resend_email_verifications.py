from django.core.management.base import BaseCommand, CommandError

from emailverification.utils import resend_verifications

class Command(BaseCommand):
	args = ''
	help = 'Re-sends verification emails that have not been clicked or killed after a certain delay, and up to three sends.'
	
	def handle(self, *args, **options):
		resend_verifications(test=False)

