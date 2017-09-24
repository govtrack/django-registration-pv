{% extends "email/template" %}
{% block content %}
Thanks for coming to {{site}}. To finish creating your account
just follow this link:

[{{return_url}}]({{return_url}})
{% endblock %}

{% block below_signature_content %}
If you did not request an account, please ignore this email and
sorry for the inconvenience. We'll send this email again in case
you missed it the first time. If you do not want to get a reminder,
please follow this link to stop future reminders:
[{{kill_url}}]({{kill_url}})
{% endblock %}
