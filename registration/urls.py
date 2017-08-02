from django.conf.urls import url

import registration.views

urlpatterns = [
    url(r'^ext/(login|associate)/start/(.+)$', registration.views.external_start, name="registration.views.external_start"),
    url(r'^ext/(login|associate)/return/(.+)$', registration.views.external_return),
    url(r'^ext/finish$', registration.views.external_finish),
    url(r'^reset-password$', registration.views.resetpassword, name="registration.views.resetpassword"),
    url(r'^ajax/login$', registration.views.ajax_login),
    url(r'^signup$', registration.views.new_user),
]
