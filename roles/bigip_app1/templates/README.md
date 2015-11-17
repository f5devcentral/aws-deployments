

This directory contains the JSON REST payload we will post to /mgmt/tm/sys/application/service to deploy a new iapp service instance from an iapp template. See app_f5_http_backport_service.json.j2

Here are the steps we followed to create this payload:

1) Deploy a new iApp through the UI
2) Query iApp via iControlREST
3) Clean up the JSON payload such that it can be reposted:
3.a) Delete selfLinks, and any other redundant or extranious fields
3.b) Change all none/None values -> ""
4) Repost as necessary

In our case we use jinja2 templating macros to customize the JSON payload for each deployment. 