from django.urls import re_path

import emailverification.views

urlpatterns = [
    re_path(r'^code/([0-9A-Z]+)$', emailverification.views.processcode),
    re_path(r'^code/delete/([0-9A-Z]+)$', emailverification.views.killcode),
    re_path(r'^ping/([a-zA-Z]+)$', emailverification.views.emailping),
]
