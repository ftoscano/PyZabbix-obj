""" 
This module is the main module of the PyZabbixObj project
"""

from __future__ import unicode_literals
import logging
import requests
import json
import inspect
from pprint import pprint

rpc_url = "/api_jsonrpc.php"
non_auth_methods = ["user.login","apiinfo.version"]
classable_types = ["groups","template","groups"]
allowed_operations = ["create","get","delete"]
allowed_objects = ["host","trigger","template","hostgroup"]
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ZabbixRequestError(Exception):
	"""
	Custom Zabbix Exception Class
	"""
	def __init__(self, value, code, message):
		self.value = value
		self.code = code
		self.message = message
	def __str__(self):
		return repr("%s , %s - Code: %s"% (self.value, self.message, self.code))	

def _json_constructor(method, auth=None, **kwargs):
	params = {}
	if kwargs is not None:
		for key, value in kwargs.iteritems():
			params[key] = value
	p = {         
		"jsonrpc":"2.0",
		"method":method,
		"id":1 ,
		"params":
			params
		}
	if auth is not None:
		p['auth'] = auth
	elif not method in non_auth_methods:
		raise ZabbixRequestError("LOGIN NOK","-1","Auth code not initialized")
	return p
		
		
class ZabbixServer(object):
	"""
	Zabbix Server Class
	
	Handle a zabbix Server. Get or write objects (not all implemented)
	
	"""
	url = None
	auth = None
	https = False
	headers = {
		"Content-Type": "application/json-rpc"
	}	
			
	def __request_wrapper__(self, func_name_object, func_name_type, **kwargs):
		logger.debug("Request wrapper: %s %s %s " % (func_name_object, func_name_type, kwargs))
	
		# "Host" on kwargs
		if allowed_objects[0] in kwargs:
			name_or_id = kwargs[allowed_objects[0]]
			search_type = allowed_objects[0]
		elif 'id' in kwargs:
			name_or_id = kwargs['id']
			search_type = func_name_object+"id"
		else:
			raise ZabbixRequestError("Programmatic Error","-1","You need to specify hostname or id in the request")
		
		json_object = _json_constructor(func_name_object+"."+func_name_type, self.auth, output="extend", selectGroups= "extend", 
						filter={search_type:name_or_id})
		response = self._request_handler(json_object)
		if len(response['result']) >0:
			# Host exists
			return eval('%s(response[\'result\'], name_or_id, server= self)' % func_name_object.title())
		else:
			# Host does not exists
			return None
		
	
	def _request_handler(self, request):
		"""
		Internal routine for Zabbix requests
		:param request: JSON string to be sent to the Zabbix Server 
		:type request: String
		:return: response of the Zabbix Server
		:rtype: String
		:raise: :class: `ZabbixRequestError` exception if error
		"""
		if self.auth is None and request['method'] != "apiinfo.version" and request['method'] != "user.login":
			raise ZabbixRequestError("LOGIN NOK","-1","User is not logged in")
		response = requests.post(self.api_server, headers=self.headers, data=json.dumps(request)).json()
		if 'error' in response:
			raise ZabbixRequestError(response['error']['data'],response['error']['code'],response['error']['message'])
		return response

	def login(self, user, pw):
		"""		
		Routine login.
		- Username/password pair will be sent once. After the returning auth code will be used
		
		:param username: Username for the Zabbix Server
		:type username: String
		:param password: Password for the Zabbix Server
		:type password: String
		:return: True if already logged, else False
		:rtype: bool
		
		:raise: :class: `ZabbixRequestError` exception if error
		"""		
		if self.auth is not None:
			return True
		json_object = _json_constructor("user.login", None, user=user, password=pw)
		login_response = self._request_handler(json_object)
		if 'result' in login_response:
			self.auth = login_response['result']
		return False
		
	
	def get_version(self):
		json_object = _json_constructor("apiinfo.version", None)
		response = self._request_handler(json_object)
		return response['result']
	
	def __init__(self, server="http://localhost/zabbix"):
		self.api_server = server+rpc_url
	
	def class_constructor(self, operation, object_type):
		return type(str("%s_%s" % (operation, object_type)),(BaseOperation,),{})
	
	def do(self, operation, object_type,**kwargs):
		if operation is not None and operation in allowed_operations and object_type is not None and object_type in allowed_objects:
			method_class = self.class_constructor(operation, object_type)
			method = method_class(self)
			return method.do(**kwargs)
		return None
		
	def __str__(self):
		return "Server Zabbix %s" % self.api_server

		
class BaseOperation(object):
	def __init__(self, server):
		name_array = self.__class__.__name__.split("_")
		self.func_name_object = name_array[1]
		self.func_name_type = name_array[0]
		self.server = server
		print "BaseOperation constructor: %s %s %s " % (self.func_name_object,self.func_name_type, server)
	
	def do(self, **kwargs):
		return self.server.__request_wrapper__(self.func_name_object,self.func_name_type,**kwargs)
		
	def __str__(self):
		return "Operator %s on %s" % (self.func_name_type, self.func_name_object)
		
	def __repr__(self):
		return self.__str__()

class GenericZabbixObject(object):
	"""
	Generic Zabbix object class. Implements some base methods
	"""
	
	def __init__(self, response, name_or_id, server, **kwargs):			
		self.server = server
		# name_or_id is an id: getting the infos from the server
		if type(name_or_id)==int or name_or_id.isdigit():
			logger.debug("%s from id" % self.__class__.__name__)
			host_results = self.get_data(name_or_id, update = True)
			if not host_results:
				raise ZabbixRequestError("Programmatic error","-1","HostGroup creation impossibile only from id")
		else:
			# name_or_id is a name
			# Check if response is null (Host does not exist)
			name = name_or_id
			self.groups = []
			if len(response)==0:
				logger.debug("Creating %s" % self.__class__.__name__ )
				# Create the host from server and populate attributes (Host does not exists)
				if 'groups' in kwargs:
					if type(kwargs['groups']) == list:
						for group in kwargs['groups']:
							self.groups.append({'groupid':group.groupid})
					elif type(kwargs['groups']) == HostGroup:
						self.groups.append({'groupid':kwargs['groups'].groupid })
					else:
						self.groups.append({'groupid':kwargs['groups']})
				logger.debug("%s" % self.groups)
				creation_response = _json_constructor(self.__class__.__name__.lower()+".create", self.server.auth, host=name, groups = self.groups)
				logger.debug("Creation: %s" % creation_response)
				response = self.server._request_handler(creation_response)
				logger.debug("Response: %s" % response)
				# Get the Host from Server and populate attributes
				id_name = self.__class__.__name__.lower()+"ids"
				self.get_data(response['result'][id_name][0], update=True)
			else:
				# Gets data from hostname (HostGroup exists)
				logger.debug("Getting %s info from name" % self.__class__.__name__)
				self.get_data_from_name(name, update=True)
			
	def __str__(self):
		return "%s %s" % (self.__class__.__name__, self.name)
			
	def __repr__(self):
		return self.__str__()
		
	def __unicode__(self):
		return self.__str__()
		
	def __update__(self, dictionary_info):
		logger.debug("Updating info...")
		if not type(dictionary_info) == dict:
			raise ZabbixRequestError("Programmatic error","-1","Error in function update")
		for (k, v) in dictionary_info.iteritems():
			# TODO: Needs to detects groups and other "classable" items
			if k in classable_types:
				pass
			setattr(self,k,v)
			logger.debug("Setting attribute for %s: %s -> %s" % (self.__class__.__name__, k,v))
			
		# Uniforming naming convention
		if 'description' in dictionary_info and not 'name' in dictionary_info:
			setattr(self,"name",self.description)
			logger.debug("Setting attribute for %s: %s -> %s" % (self.__class__.__name__, "name",self.description))
			
	def __get_data__(self, id_type, id, update):
		logger.debug("Getting data for %s" % self.__class__.__name__)
		output = None
		creation_response = _json_constructor(self.__class__.__name__.lower()+".get", self.server.auth, output="extend", filter={id_type:id})
		response = self.server._request_handler(creation_response)
		# Get the Host from Server and populate attributes
		if len(response['result']) > 0:
			output = response['result'][0]
			logger.debug("Response: %s " % output)
			if update:
				self.__update__(output)
		return output
		
	def __get_data_from_name__(self, name_type, name, update):
		logger.debug("Getting data from hostname for %s " % self.__class__.__name__)
		creation_response = _json_constructor(self.__class__.__name__.lower()+".get", self.server.auth, output="extend", filter={name_type:name})
		response = self.server._request_handler(creation_response)
		if update:
			self.__update__(response['result'][0])
		return response['result']	
		
					
	def __dict__(self, *args):
		out = []
		for v in args:
			out.append(v)
		return out

class Hostgroup(GenericZabbixObject):
	"""		
	Host Group Class
	
	:param response: JSON string to be sent or received from the Zabbix Server 
	:type response: String
	:param name_or_id: name or id of the object
	:type name_or_id: String
	:param server: Zabbix server
	:type server: ZabbixServer
	
	:raise: :class: `ZabbixRequestError` exception if error
	"""	

	def __init__(self, response, name_or_id, server):			
		super(type(self),self).__init__(response, name_or_id, server)
		
	def get_data(self, id, update):
		return super(type(self),self).__get_data__("groupid",id, update)

	def get_data_from_name(self, name, update):
		return super(type(self),self).__get_data_from_name__("name", name, update)
		
		
class Trigger(GenericZabbixObject):
	"""		
	Trigger Class
	
	:param response: JSON string to be sent or received from the Zabbix Server 
	:type response: String
	:param name_or_id: name or id of the object
	:type name_or_id: String
	:param server: Zabbix server
	:type server: ZabbixServer
	
	:raise: :class: `ZabbixRequestError` exception if error
	"""	

	def __init__(self, response, name_or_id, server):			
		super(type(self),self).__init__(response, name_or_id, server)
		
	def get_data(self, id, update):
		datas = super(type(self),self).__get_data__("triggerid", id, update)
		return datas

	def get_data_from_name(self, name, update):
		raise ZabbixRequestError("Programmatic error","-1","Trigger search not possible for name")
		#return super(type(self),self).__get_data_from_name__("host", name, update)
		

class Template(GenericZabbixObject):
	"""
	Template Class
	
	:param response: JSON string to be sent or received from the Zabbix Server 
	:type response: String
	:param name_or_id: name or id of the object
	:type name_or_id: String
	:param server: Zabbix server
	:type server: ZabbixServer

	:raise: :class: `ZabbixRequestError` exception if error
	"""
	
	def __init__(self, response, name_or_id, server, **kwargs):			
		super(type(self),self).__init__(response, name_or_id, server, **kwargs)
		
	def get_data(self, id, update):
		datas = super(type(self),self).__get_data__("templateids",id,  update)
		return datas

	def get_data_from_name(self, name, update):
		return super(type(self),self).__get_data_from_name__("host", name, update)

class Host(GenericZabbixObject):
	"""
	Host Class
	
	:param response: JSON string to be sent or received from the Zabbix Server 
	:type response: String
	:param hostname_or_id: hostname or id of the object
	:type hostname_or_id: String
	:param server: :class:`ZabbixServer` instance
	:type server: ZabbixServer  
	:param Interfaces: Not implemented yet! (optional) :class:`Interface` instance
	:type Interfaces: :class:`Interface` or :class:`list` of :class:`Interface`
	:param HostGroups: (optional) :class:`HostGroup` instance
	:type HostGroup: :class:`HostGroup` or :class:`list` of :class:`HostGroup` 
	:param Template: (optional) :class:`Template` instance
	:type Template: :class:`Template` or :class:`list` of :class:`Template` 
	
	:raise: :class: `ZabbixRequestError` exception if error
	"""
	standard_interface = {
					"type": 1,
					"main": 1,
					"useip": 1,
					"ip": "127.0.0.1",
					"dns": "",
					"port": "10050"}
	interfaces = [standard_interface]
	groups = []
	templates = []
	
	def __init__(self, response, hostname_or_id, server, **kwargs):
		"""
		Host init method has been overridden due to different implementation
		"""
		self.server = server
		# hostname_or_id is an id: getting the infos from the server
		if type(hostname_or_id)==int or hostname_or_id.isdigit():
			logger.debug("Host from id")
			host_results = self.get_data(hostname_or_id, update = True)
			if not host_results:
				raise ZabbixRequestError("Programmatic error","-1","Host creation impossibile only from id")
		# hostname_or_id is an hostname
		else:
			# Check if response is null (Host does not exist)
			hostname = hostname_or_id
			if 'interfaces' in kwargs:
				self.interfaces = []
				for interface in kwargs['interfaces']:
					self.interfaces.append(interface)
					
			if 'groups' in kwargs:
				self.groups = []
				if type(kwargs['groups']) == list:
					for group in kwargs['groups']:
						self.groups.append(group.groupid)
				else:
					self.groups.append(kwargs['groups'].groupid)
					
			if 'templates' in kwargs:
				self.templates = []
				if type(kwargs['templates']) == list:
					for template in kwargs['templates']:
						self.templates.append(template.templateid)
				else:
					self.templates.append(kwargs['templates'].templateid)
					
			if len(response)==0:
				logger.debug("Creating host")
				# Create the host from server and populate attributes (Host does not exists)
				creation_response = _json_constructor("host.create", self.server.auth, host=hostname, interfaces=self.interfaces, 
				groups = self.groups,templates=self.templates)
				response = self.server._request_handler(creation_response)
				# Get the Host from Server and populate attributes
				self.get_data(self.get_data(response['result']['hostids'][0]), update=True)
			else:
				# Gets data from hostname (Host exists)
				logger.debug("Getting host info from hostname")
				self.get_data_from_hostname(hostname, update=True)
	
	def get_data(self, id, update=False):
		return super(type(self),self).__get_data__("hostid",id, update = update)

	def get_data_from_hostname(self, hostname, update=False):
		logger.debug("Getting data from hostname")
		return super(type(self),self).__get_data_from_name__("host", hostname, update=update)
		
		
