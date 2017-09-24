{% extends "email/template" %}
{% block content %}
You requested to change your {{site}} account email address. To
continue, please follow this link:

[{{return_url}}]({{return_url}})

If it was not you who requested the change for this email address,
just ignore this email.
{% endblock %}

{% block below_signature_content %}
If you did not request a change in your email address, please ignore this email and
apologies for the inconvenience. We'll send this email again in case
you missed it the first time. If you do not want to get a reminder,
please follow this link to stop future reminders:
[{{kill_url}}]({{kill_url}})
{% endblock %}
