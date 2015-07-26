from models import *
from django.contrib import admin

class RecordAdmin(admin.ModelAdmin):
	readonly_fields = ("email", "code", "searchkey", "action")
	search_fields = ["email"]
	list_display = ["created", "email", "link", "description"]

	def link(self, obj):
		return obj.url()

	def description(self, obj):
		return unicode(obj.get_action())

class PingAdmin(admin.ModelAdmin):
	readonly_fields = ("user",)
class BouncedEmailAdmin(admin.ModelAdmin):
	readonly_fields = ("user",)

admin.site.register(Record, RecordAdmin)
admin.site.register(Ping, PingAdmin)
admin.site.register(BouncedEmail, BouncedEmailAdmin)
