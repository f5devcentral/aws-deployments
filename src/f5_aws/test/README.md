# README.md

These tests should be run before checking code into the master branch on the public github account. You are responsible for this, as there is no CI framework for this code. 

Proper testing will ensure the scripts provided in are kept in working order.

Run tests (from the top-level directory) via:
(venv)vagrant@f5demo:/aws-deployments$ py.test ./src/f5_aws/test

to run a specific test:
py.test ./src/f5_aws/test/test_deployments.py


# Here are, in general, what we want to cover via tests (manual or automated):
1) Test that the images are available in the regions we specify (test_images.py)
2) Test that all the CFTs we are using are valid (test_cfts.py)
3) Test a simple, single standalone deployment model. 
4) Test deployment path where deploy_analytics=true and where deploy_analytics=False
	-when analytics is deployed, `info login` shows the URL to reach analytics host
	-when analytics not deployed, value for 'analyticshost' key in `info login` output is null
5) Test deployment path where deployment_type='lb_only' and where deployment_type='lb_and_waf'
	-when 'lb_only', better licensing package is used, only ltm and avr provisioned
	-when 'lb_and_waf', best licensing package is used, asm, ltm, avr provisioned, curl against VIP produces blocking page for vulnerabilities
6) Test the GTM clustering path
	-when multiple GTMs are deployed, what do we check?
7) Test the BIG-IP DSC clustering path (same-zone clustering)
	-when BIG-IP DSC is deployed, TMOS configuration objects created on one BIG-IP are replicated to the other.
8) Test when GTM deployed, WideIP is in output for `info login`
	-when GTM and a client host are deployed, running the `start_traffic` command should generate metrics in AVR or Splunk. The JMeter client hits a WideIP exposed by GTM.

Unfortunately, these tests are expensive....

As an example, consider the costs for running test #6
4 BIG-IP Better, 25Mpbs:
	EC2 instance footprint (m3.xlarge): 	$0.266/hr x 4  
	BIG-IP Better utility license:      	$0.83/hr x 4  
	Total:									$1.096/hr x 4 = $4.384

2 App hosts
	EC2 instance footprint (m3.medium):		$0.067 x 2
	License:								$0.0/hr
	Total:									$0.067/hr x 2 = $0.134

1 Client host
	EC2 instance footprint (m3.medium):		$0.067/hr
	License:								$0.0/hr
	Total:									$0.067 

1 Enterprise Spunk host
	EC2 instance footprint (m3.medium):		$0.105/hr 
	License:								$0.0/hr
	Total:									$0.105 

Total for all for 1 hr = $4.69


We ignore EBS storage costs as they are neglibable. $0.10 /GB-month
