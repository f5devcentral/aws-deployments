

This directory contains the JSON REST payload we will post to /mgmt/tm/sys/application/template to deploy a new iApp template. See app_f5_http_backport_template.json

Here are the steps we following for this particular iApp template:

1) Download the template from DevCentral codeshare or otherwise. 
2) Make sure the iApp doesn't contain any TCL packages in the .tmpl file, if so, resolve these issues... :(
3) Import the payload via the Configuration Utility (GUI)
3.a) Export to JSON via iControlRest - https://52.22.206.179/mgmt/tm/sys/application/template/f5.http.backport.1.1.2?expandSubcollections=true
3.b) Remove extanious fields like "selfLink", "generation", etc
3.c Rename field actionsReference -> actions
4) Repost as necessary
