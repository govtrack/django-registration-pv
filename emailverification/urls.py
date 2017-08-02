from django.conf.urls import url

import emailverification.views

urlpatterns = [
    url(r'^code/([0-9A-Z]+)$', emailverification.views.processcode),
    url(r'^code/delete/([0-9A-Z]+)$', emailverification.views.killcode),
    url(r'^ping/([a-zA-Z]+)$', emailverification.views.emailping),
]