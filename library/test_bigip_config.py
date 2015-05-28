#from bigip_config import BigipConfig


class Module(object):
    def __init__(self, **kwargs):
    	self.params = {}
    	for k, v in kwargs.iteritems():
    		self.params[k] = v

m = Module(a=1, b=2)
print m.params["a"]
    	    

   
# try a get



# try a post where not object exists


# try a post on the same object - should pass



