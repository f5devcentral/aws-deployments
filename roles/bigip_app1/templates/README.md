Creating the iApp for deploying via iControlRest

Steps to create this template below:
1) create the iApp through the UI
2) query iApp in json via iControlREST
3) clean up json such that it can be reposted:
.a) delete self references in the json payload
.b) change all none/None  values -> ""
4) Templatize as necessary.  In our example, we have just made the pool_addr a variable