#!/usr/bin/python3
# Matrix

# Matrix notification script from @beposec inspired by:
# Telegram_Notification from Stefan Gehn stefan+cmk@srcxbox.net
# check_mk_matrix_notifications from Stanislav N. aka pztrn

# Tested with Checkmk 2.0.0p17 on Debian Bullseye.

import os
import json
import re
import sys
import string
import urllib
import urllib.request
import urllib.parse
import random
import ssl

#################################################################
# Configure Matrix Connection here:
MATRIXHOST = ''
MATRIXTOKEN = ''
#################################################################
# Room id is set by Checkmk notification rule parameter
MATRIXROOM = os.environ["NOTIFY_PARAMETER_1"]
#################################################################

# Setup context for ssl certificate validation
sslverify = ssl.create_default_context(capath="/etc/ssl/certs/")

# Prepare Message Template for Host Notifications
tmpl_host_text = """<b>Check_MK: $HOSTNAME$ - $EVENT_TXT$</b>
<pre><code>Host:     $HOSTNAME$
Alias:    $HOSTALIAS$
Address:  $HOSTADDRESS$
Event:    $EVENT_TXT$
Output:   $LONGHOSTOUTPUT$
Comment:  $NOTIFICATIONCOMMENT$
</code></pre>\n
"""
# Prepare Message Template for Service Notifications
tmpl_service_text = """<b>Check_MK: $HOSTNAME$/$SERVICEDESC$ $EVENT_TXT$</b>
<pre><code>Host:     $HOSTNAME$
Alias:    $HOSTALIAS$
Address:  $HOSTADDRESS$
Service:  $SERVICEDESC$
Event:    $EVENT_TXT$
Output:   $LONGSERVICEOUTPUT$
Comment:  $NOTIFICATIONCOMMENT$
</code></pre>\n
"""


def validate_room_id(MATRIXROOM):
    # Validation of given room id
    room_id_pattern = (r"(![a-zA-Z]+):(([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,})")
    if not re.match(room_id_pattern, MATRIXROOM):
        sys.exit(
            "The given value '%s' is not a proper [matrix] room id."
            % MATRIXROOM
        )


def substitute_context(template, context):
    # Replace all known variables
    for varname, value in context.items():
        template = template.replace('$'+varname+'$', value)

    # Remove unused variables and make them empty
    template = re.sub(r"\$[A-Z_][A-Z_0-9]*\$", "", template)
    return template


def construct_message_text(context):
    notification_type = context["NOTIFICATIONTYPE"]
    if notification_type in ["PROBLEM", "RECOVERY"]:
        txt_info = "$PREVIOUS@HARDSHORTSTATE$ -> $@SHORTSTATE$"
    elif notification_type.startswith("FLAP"):
        if "START" in notification_type:
            txt_info = "Started Flapping"
        else:
            txt_info = "Stopped Flapping ($@SHORTSTATE$)"
    elif notification_type.startswith("DOWNTIME"):
        what = notification_type[8:].title()
        txt_info = "Downtime " + what + " ($@SHORTSTATE$)"
    elif notification_type == "ACKNOWLEDGEMENT":
        txt_info = "Acknowledged ($@SHORTSTATE$)"
    elif notification_type == "CUSTOM":
        txt_info = "Custom Notification ($@SHORTSTATE$)"
    else:
        txt_info = notification_type  # Should neven happen

    txt_info = substitute_context(
        txt_info.replace("@", context["WHAT"]),
        context
    )

    context["EVENT_TXT"] = txt_info

    if context['WHAT'] == 'HOST':
        tmpl_text = tmpl_host_text
    else:
        tmpl_text = tmpl_service_text

    return substitute_context(tmpl_text, context)


def fetch_notification_context():
    context = {}
    for (var, value) in os.environ.items():
        if var.startswith("NOTIFY_"):
            context[var[7:]] = value
    return context


def send_matrix_message(text):
    # Build Matrix Message
    matrixDataDict = {
        "msgtype": "m.text",
        "body": text,
        "format": "org.matrix.custom.html",
        "formatted_body": text,
    }
    matrixData = json.dumps(matrixDataDict)
    matrixData = matrixData.encode("utf-8")

    # Create random transaction ID for Matrix Homeserver
    txnId = ''.join(random.SystemRandom().choice(
        string.ascii_uppercase + string.digits) for _ in range(16))
    # Authorization headers and etc.
    matrixHeaders = {"Authorization": "Bearer " + MATRIXTOKEN,
                     "Content-Type": "application/json",
                     "Content-Length": str(len(matrixData))}
    # Request
    url = MATRIXHOST \
        + "/_matrix/client/r0/rooms/" \
        + MATRIXROOM \
        + "/send/m.room.message/" \
        + txnId
    req = urllib.request.Request(
        url,
        data=matrixData,
        headers=matrixHeaders,
        method='PUT'
    )
    try:
        response = urllib.request.urlopen(req, context=sslverify)
    except urllib.error.URLError as e:
        sys.stdout.write(
            'Cannot send to matrix room: HTTP-Error %s %s\n' % (e.reason, e)
        )


def main():
    validate_room_id(MATRIXROOM)
    context = fetch_notification_context()
    text = construct_message_text(context)
    send_matrix_message(text)


if __name__ == '__main__':
    main()
