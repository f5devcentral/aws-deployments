#!/bin/bash

# Set these variables from output of CFT
MgmtIP=52.23.93.16
ExternalSelfIP=172.16.13.186   #External/Public Private IP
InternalSelfIP=172.16.12.39    #Internal/Private Private IP 
RESTPassword="XXXXXXXXXX"
# and run 
# bash ./rest_commands.sh
# to print commands

echo -e "\n#Disable GUI Setup"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X PATCH -d '{"value":"false"}' https://$MgmtIP/mgmt/tm/sys/db/setup.run | python -m json.tool
#Prints to use environmental variables
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X PATCH -d '{\"value\":\"false\"}' https://\$MgmtIP/mgmt/tm/sys/db/setup.run | python -m json.tool"
#Prints to use variables set above
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X PATCH -d '{\"value\":\"false\"}' https://$MgmtIP/mgmt/tm/sys/db/setup.run | python -m json.tool"

echo -e "\n#Create public vlan"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X POST -d '{"name":"public", "interfaces":"1.1"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"public\", \"interfaces\":\"1.1\"}' https://\$MgmtIP/mgmt/tm/net/vlan | python -m json.tool"
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"public\", \"interfaces\":\"1.1\"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool"

echo -e "\n#Create private vlan"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X POST -d '{"name":"private", "interfaces":"1.2"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"private\", \"interfaces\":\"1.2\"}' https://\$MgmtIP/mgmt/tm/net/vlan | python -m json.tool"
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"private\", \"interfaces\":\"1.2\"}' https://$MgmtIP/mgmt/tm/net/vlan | python -m json.tool"

echo -e "\n#Create public SelfIP"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X POST -d '{"name":"public_self", "address":"$172.16.13.184/24", "vlan":"public"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"public_self\", \"address\":\"\${ExternalSelfIP}/24\", \"vlan\":\"public\"}' https://\$MgmtIP/mgmt/tm/net/self | python -m json.tool"
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"public_self\", \"address\":\"${ExternalSelfIP}/24\", \"vlan\":\"public\"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool"

echo -e "\n#Create private SelfIP"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X POST -d '{"name":"private_self", "address":"172.16.12.39/24", "vlan":"private"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"private_self\", \"address\":\"\${InternalSelfIP}/24\", \"vlan\":\"private\"}' https://\$MgmtIP/mgmt/tm/net/self | python -m json.tool"
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"private_self\", \"address\":\"${InternalSelfIP}/24\", \"vlan\":\"private\"}' https://$MgmtIP/mgmt/tm/net/self | python -m json.tool"

echo -e "\n#Create Pool"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X POST -d '{ "name": " vs1_pool", "members":[ {"name":"172.16.12.201:80","address":"172.16.12.201"} ], "monitor": "http" }' https://$MgmtIP/mgmt/tm/ltm/pool | python -m json.tool
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"vs1_pool\",\"members\":[{\"name\":\"172.16.12.201:80\",\"address\":\"172.16.12.201\"}],\"monitor\":\"http\"}' https://\$MgmtIP/mgmt/tm/ltm/pool | python -m json.tool"
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X POST -d '{\"name\":\"vs1_pool\",\"members\":[{\"name\":\"172.16.12.201:80\",\"address\":\"172.16.12.201\"}],\"monitor\":\"http\"}' https://$MgmtIP/mgmt/tm/ltm/pool | python -m json.tool"

echo -e "\n#Create iApp (Edit http_generic_payload.json first)"
#curl -sk -u restadmin:'$RESTPassword' -H "Content-type: application/json" -X POST -d @http_generic_iApp_payload.json https://$MgmtIP/mgmt/tm/sys/application/service | python -m json.tool
#echo "curl -sk -u restadmin:'\$RESTPassword' -H \"Content-type: application/json\" -X POST -d @http_generic_iApp_payload.json https://\$MgmtIP/mgmt/tm/sys/application/service | python -m json.tool"
echo "curl -sk -u restadmin:'$RESTPassword' -H \"Content-type: application/json\" -X POST -d @http_generic_iApp_payload.json https://$MgmtIP/mgmt/tm/sys/application/service | python -m json.tool"

