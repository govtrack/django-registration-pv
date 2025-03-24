from django.urls import re_path

import registration.views

urlpatterns = [
    re_path(r'^ext/(login|associate|verify)/start/(.+)$', registration.views.external_start, name="registration.views.external_start"),
    re_path(r'^ext/(login|associate|verify)/return/(.+)$', registration.views.external_return),
    re_path(r'^ext/finish$', registration.views.external_finish),
    re_path(r'^reset-password$', registration.views.resetpassword, name="registration.views.resetpassword"),
    re_path(r'^ajax/login$', registration.views.ajax_login),
    re_path(r'^signup$', registration.views.new_user),
]
