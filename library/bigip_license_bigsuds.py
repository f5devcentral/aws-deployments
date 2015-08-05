#!/usr/bin/env python
'''
----------------------------------------------------------------------------
The contents of this file are subject to the "END USER LICENSE AGREEMENT FOR F5
Software Development Kit for iControl"; you may not use this file except in
compliance with the License. The License is included in the iControl
Software Development Kit.
 
Software distributed under the License is distributed on an "AS IS"
basis, WITHOUT WARRANTY OF ANY KIND, either express or implied. See
the License for the specific language governing rights and limitations
under the License.
 
The Original Code is iControl Code and related documentation
distributed by F5.
 
The Initial Developer of the Original Code is F5 Networks,
Inc. Seattle, WA, USA. Portions created by F5 are Copyright (C) 1996-2004 F5 Networks,
Inc. All Rights Reserved.  iControl (TM) is a registered trademark of F5 Networks, Inc.
 
Alternatively, the contents of this file may be used under the terms
of the GNU General Public License (the "GPL"), in which case the
provisions of GPL are applicable instead of those above.  If you wish
to allow use of your version of this file only under the terms of the
GPL and not to allow others to use your version of this file under the
License, indicate your decision by deleting the provisions above and
replace them with the notice and other provisions required by the GPL.
If you do not delete the provisions above, a recipient may use your
version of this file under either the License or the GPL.
----------------------------------------------------------------------------
'''
 
def usage ():
    print "Usage:"
    print "%s --bigip <IP|hostname> --username <username> --password <password> --server <license_server_hostname> \
           --reg_keys <regkeys> --license <license_file> --eula <eula_file>" % sys.argv[0]
    print "ex. "
    print "   Will attempt to re-license with existing keys on unit using license server activate.f5.com"
    print "     %s --bigip 192.168.1.245 --username admin" % sys.argv[0]
    print "   Will attempt to re-license with provided reg_keys CSV string using license server activate.f5.com"
    print "     %s --bigip 192.168.1.245 --username admin --reg_keys \"XXXX-XXXX-XXXX-XXXX,XXXX-XXXX,XXXX-XXXX\" " % sys.argv[0]
 
 
 
 
def get_license_from_F5_License_Server ( server_hostname, dossier_string, eula_string, email,
                                         firstName, lastName, companyName, phone, jobTitle,
                                        address, city, stateProvince, postalCode, country ):
 
    try:
 
        license_string = ""
        # Unfortunately, F5 wsdl on license server references http but F5 only accepts https so as an ugly workaround need to
        # download wsdl, save to disk, replace links http with https, and have SUDS client reference local file instead
        #(eg. url = "file:///home/admin/f5wsdl.xml")
 
        download_url = "https://" + server_hostname + "/license/services/urn:com.f5.license.v5b.ActivationService?wsdl"
 
        # Check to see if there's a copy of wsdl file on disk first
        # Careful with this behavior if you switch server hostnames.
        local_wsdl_file_name = str(server_hostname) + '-f5wsdl-w-https.xml'
        wsdl_data = []
 
        try:
            with open(local_wsdl_file_name, 'r') as fh_wsdl:
                wsdl_data = fh_wsdl.read()
        except:
            print "Can't find a locally stored WSDL file."
 
 
        if not wsdl_data:
            print "Attempting to fetch wsdl online."
            f5wsdl = urllib2.urlopen(download_url)
            newlines = []
            for line in f5wsdl:
                # do the replacing here
                newlines.append(line.replace('http://' + server_hostname , 'https://' + server_hostname))
 
            fh_local = open(local_wsdl_file_name,'w')
            fh_local.writelines(newlines)
            fh_local.close()
 
        # put url going to pass to client in file format
        url = "file:" + urllib.pathname2url(os.getcwd()) + "/" +  local_wsdl_file_name
 
        #Now create client object using wsdl from disk instead of the interwebs.
        client = Client(url)
 
        # NOT using below as will just try actually licensing and fail then if needed
        # try:
        #    # ping() method should return string containing date
        #    print "Checking License Service Reachability..."
        #    return_ping_date = client.service.ping()
        # except:
        #    print "License SOAP service unreachable. Check network connectivity."
        #    return
 
 
        transaction = client.factory.create('ns0:LicenseTransaction')
        # If eula isn't present on first call to getLicense, transaction will fail
        # but it will return a eula after first attempt
        transaction = client.service.getLicense(
                                                dossier = dossier_string,
                                                eula = eula_string,
                                                email = email,
                                                firstName = firstName ,
                                                lastName = lastName,
                                                companyName = companyName,
                                                phone = phone,
                                                jobTitle = jobTitle,
                                                address = address,
                                                city = city,
                                                stateProvince = stateProvince,
                                                postalCode = postalCode,
                                                country = country,
                                                )
 
        #Extract the eula offered from first try
        eula_string = transaction.eula
 
        if transaction.state == "EULA_REQUIRED":
            #Try again, this time with eula populated
            transaction = client.service.getLicense(
                                                        dossier = dossier_string,
                                                        eula = eula_string,
                                                        email = email,
                                                        firstName = firstName ,
                                                        lastName = lastName,
                                                        companyName = companyName,
                                                        phone = phone,
                                                        jobTitle = jobTitle,
                                                        address = address,
                                                        city = city,
                                                        stateProvince = stateProvince,
                                                        postalCode = postalCode,
                                                        country = country,
                                                        )
 
        if transaction.state == "LICENSE_RETURNED":
            license_string = transaction.license
        else:
            print "Can't retrieve license from Licensing server"
            print "License server returned error: Number:" + str(transaction.fault.faultNumber) + " Text: " + str(transaction.fault.faultText)
 
        return license_string
 
    except:
        print "Can't retrieve License from Server"
        traceback.print_exc(file=sys.stdout)
 
 
 
def get_reg_keys(obj):
 
    try:
 
        reg_keys = []
        reg_keys = obj.Management.LicenseAdministration.get_registration_keys()
        return reg_keys
 
    except:
        print "Get Reg Keys error. Check log."
        traceback.print_exc(file=sys.stdout)
 
 
 
def get_dossier (obj, reg_keys ):
 
    try:
 
        dossier_string = obj.Management.LicenseAdministration.get_system_dossier ( reg_keys )
        return dossier_string
 
    except:
        print "Get Dossier error. Check log."
        traceback.print_exc(file=sys.stdout)
 
 
def get_eula_file (obj):
 
    try:
 
        eula_char_array = obj.Management.LicenseAdministration.get_eula_file( )
        eula_string =  base64.b64decode(eula_char_array)
        return eula_string
 
    except:
        print "Get eula_file. Check log."
        traceback.print_exc(file=sys.stdout)
 
 
 
def install_license (obj, license_string ):
 
    try:
 
        license_char_array = base64.b64encode(license_string)
        obj.Management.LicenseAdministration.install_license ( license_file_data = license_char_array )
 
    except:
        print "Install License error. Check log."
        traceback.print_exc(file=sys.stdout)
 
 
def get_license_status (obj):
 
    try:
 
        license_status = obj.Management.LicenseAdministration.get_license_activation_status()
        return license_status
 
    except:
        print "Get License Status error. Check log."
        traceback.print_exc(file=sys.stdout)
 
 
### IMPORT MODULES ###
import os
import sys
import time
import traceback
import base64
import urllib
import urllib2
import getpass
from suds.client import Client
from optparse import OptionParser
 
import bigsuds
 
 
# from suds import WebFault
# import logging
 
# logging.getLogger('suds.client').setLevel(logging.DEBUG)
# logging.getLogger('suds.metrics').setLevel(logging.DEBUG)
# logging.getLogger('suds').setLevel(logging.DEBUG)
 
#### SET CONFIG VARIABLES ####
 
 
#Misc EULA Variables
email  = "example.icontrol@example.com"
firstName = "example"
lastName = "icontrol"
companyName = "Example"
phone = "111-111-1111"
jobTitle = "DEV OPS"
address = "111 EXAMPLE ICONTROL RD"
city = "Seattle"
stateProvince = "WA"
postalCode = "98119"
country = "United States"
 
 
parser = OptionParser()
parser.add_option("-b", "--bigip", action="store", type="string", dest="bigips", default="192.168.1.245")
parser.add_option("-u", "--username", action="store", type="string", dest="uname", default="admin")
parser.add_option("-p", "--password", action="store", type="string", dest="upass", default="admin")
parser.add_option("-s", "--server", action="store", type="string", dest="server_hostname", default="activate.f5.com" )
parser.add_option("-r", "--reg_keys", action="store", type="string", dest="reg_keys_string" )
parser.add_option("-l", "--license", action="store", type="string", dest="local_license_file_name")
parser.add_option("-e", "--eula", action="store", type="string", dest="local_eula_file_name")
(options, args) = parser.parse_args()
 
### INITIALIZE BIGIP OBJECT ###
 
if options.bigips and options.uname and not options.upass:
    print "Enter your password for username: %s" % options.uname
    upass = getpass.getpass()
elif options.bigips and options.uname:
    pass
else:
    usage()
    sys.exit()
 
# Can re-license a list of BIG-IPs IF you don't provide a list of regkeys on CLI. 
# As reg key split function does not accommodate list of keys for multiple devices.
 
if options.bigips:
    bigip_list = options.bigips.split(",")
 
for i in bigip_list:
 
    print "\nAttempting to License BIGIP " + i
 
    reg_keys = []
    license_string = ""
    eula_string = ""
    reg_keys_string = ""
    local_license_file_name = ""
    local_eula_file_name = ""
    server_hostname = options.server_hostname
    uname = options.uname
    upass = options.upass

    b = bigsuds.BIGIP(
	    hostname = i,
	    username = uname,
	    password = upass,
	    )
 
 
    ########## START MAIN LOGIC ######
 
 
 
    if local_license_file_name:
	try:
	    print "Attempting to retrive License from local disk ..."
	    with open(local_license_file_name, 'r') as fh_license:
		license_string = fh_license.read()
 
	except:
	    print "Can't Open license file named: \"" + local_license_file_name + "\" on disk."
	    #sys.exit()
	    print "No worries. Will attempt to retrieve one from online."
 
 
    if not license_string:
 
	print "Attempting to get license online."
	print "License server requires you to submit EULA."
	if options.local_eula_file_name:
	    print "Attempting to retrive EULA from local disk first..."
	    try:
		with open(options.local_eula_file_name, 'r') as fh_eula:
		    eula_string = fh_eula.read()
 
	    except:
		print "Can't find EULA file named : \"" +  options.local_eula_file_name + "\" on disk."
		print "No worries. Will attempt to retrieve one during transaction with License Server."
 
    # Could also try seeing if Target BIG-IP has one stored
    # eula_file = get_eula_file(b)
 
 
    if options.reg_keys_string:
	reg_keys = options.reg_keys_string.split(",")
	print "reg keys provided"
	print reg_keys
 
    if len(reg_keys) < 1:
	    print "Reg Key list is empty, attempting to retrieve existing keys from the unit"
	    reg_keys = get_reg_keys(b)
 
 
    print "Getting dossier using keys:" + str(reg_keys)
    dossier_string = get_dossier( b, reg_keys )
    # print "dossier = " + str(dossier_output)
 
 
    license_string = get_license_from_F5_License_Server(
							options.server_hostname,
							dossier_string,
							eula_string,
							email,
							firstName,
							lastName,
							companyName,
							phone,
							jobTitle,
							address,
							city,
							stateProvince,
							postalCode,
							country
							)
 
    if license_string:
	print "License Found. Attempting to installing License on BIGIP:"
	install_license ( b, license_string )
    else:
	print "Sorry. Could not retrieve License. Check your connection"
 
    license_status = get_license_status ( b )
    print "License status = " + str(license_status)

