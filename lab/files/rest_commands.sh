#!/bin/bash

#Edit these variables
MgmtIP=52.23.93.16
PublicSelfIP=172.16.13.186
PrivateSelfIP=172.16.12.39
RESTPassword="XXXXXXXXXX"
#and run 
# bash ./rest_commands.sh
# to print commands

echo -e "\nDisable GUI Setup" 
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X PATCH -d '{"value":"false"}' https://$MgmtIP/mgmt/tm/sys/db/setup.run | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X PATCH -d '{\"value\":\"false\"}' https://$MgmtIP/mgmt/tm/sys/db/setup.run | python -m json.tool"

echo -e "\nCreate public vlan"
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{"name":"public", "interfaces":"1.1"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{\"name\":\"public\", \"interfaces\":\"1.1\"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool"

echo -e "\nCreate private vlan"
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{"name":"private", "interfaces":"1.2"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{\"name\":\"private\", \"interfaces\":\"1.2\"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool"

echo -e "\nCreate public SelfIP"
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{"name":"public_self", "address":"172.16.13.186/24", "vlan":"public"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{\"name\":\"public_self\", \"address\":\"172.16.13.186/24\", \"vlan\":\"public\"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool"

echo -e "\nCreate private SelfIP"
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{"name":"private_self", "address":"172.16.12.39/24", "vlan":"private"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{\"name\":\"private_self\", \"address\":\"172.16.12.39/24\", \"vlan\":\"private\"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool"

echo -e "\nCreate Pool"
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{ "name": " vs1_pool", "members":[ {"name":"172.16.12.201:80","address":"172.16.12.201"} ], "monitor": "http" }' https://$MgmtIP/mgmt/tm/ltm/pool | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d '{\"name\":\"vs1_pool\",\"members\":[{\"name\":\"172.16.12.201:80\",\"address\":\"172.16.12.201\"}],\"monitor\":\"http\"}' https://$MgmtIP/mgmt/tm/ltm/pool | python -m json.tool"

echo -e "\nCreate iApp"
#curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d @http_generic_iApp_payload.json https://$MgmtIP/mgmt/tm/sys/application/service | python -m json.tool
echo "curl -sk -u restadmin:'$RESTPassword' -H Content-type: application/json -X POST -d @http_generic_iApp_payload.json https://$MgmtIP/mgmt/tm/sys/application/service | python -m json.tool"


