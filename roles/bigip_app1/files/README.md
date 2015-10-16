

This directory contains the JSON REST payload we will post to /mgmt/tm/sys/application/template to deploy a new iApp template. See app_f5_http_backport_template.json

Here are the steps we following for this particular iApp template:

1) Download the template from DevCentral codeshare or otherwise. 
2) Make sure the iApp doesn't contain any packages in the .tmpl file, if so, resolve these issues... :(
3) Import the payload via the Configuration Utility (GUI)
3.a) Export to JSON via iControlRest
3.b) Remove extanious fields like "selfLink", "generation", etc
4) Repost as necessary
