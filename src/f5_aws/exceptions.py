# exceptions.py

# some custom exceptions that we can catch 

class ValidationError(Exception):
	pass

class ExecutionError(Exception):
	pass

class LifecycleError(Exception):
	pass