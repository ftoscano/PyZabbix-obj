""" 
This module is the main module of the PyZabbixObj project
"""

from __future__ import unicode_literals
import logging
import requests
import json
from pprint import pprint

rpc_url = "/api_jsonrpc.php"
non_auth_methods = ["user.login","apiinfo.version"]
classable_types = ["groups"]
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ZabbixRequestError(Exception):
	"""
	Custom Zabbix Exception Class
	
	Handle a zabbix Server. Get or write objects (not all implemented)
	
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
	
	def __init__(self, server):
		self.api_server = server+rpc_url

	def get_host(self, hostname):
		json_object = _json_constructor("host.get", self.auth, output="extend", selectGroups= "extend", 
						filter={"host":hostname})
		response = self._request_handler(json_object)
		return Host(response['result'], hostname = hostname, server = self )

	def get_hostgroup(self, name):
		json_object = _json_constructor("hostgroup.get", self.auth, output="extend", 
						filter={"name":name})
		response = self._request_handler(json_object)
		return HostGroup(response['result'], name, server= self)
		
	def get_hosts(self, hostnames):
		# Check if hostname is a single hostname (String)
		if type(hostnames) is str:
			hostnames = [hostnames]
		json_object = _json_constructor("host.get", self.auth, output="extend", selectGroups= "extend", 
						filter={"host":hostnames})
		response = self._request_handler(json_object)
		hosts = []
		for results in response['result']:
			hosts.append(Host(results, None))	# TO FIX
		return hosts

	def get_or_create_host(self, hostname, **kwargs):
		# Get the object from the DB
		json_object = _json_constructor("host.get", self.auth, output="extend", selectGroups= "extend", 
						filter={"host":hostname})
		response = self._request_handler(json_object)
		return Host(response['result'],hostname_or_id = hostname, server= self, **kwargs)
	
	def get_template(self, name):
		json_object = _json_constructor("template.get", self.auth, output="extend", 
						filter={"host":name})
		response = self._request_handler(json_object)
		return Template(response['result'], name, server= self)
		
	def __str__(self):
		return "Server Zabbix %s" % self.url



class HostGroup(object):
	"""		
	Host Group Class
	
	:param response: JSON string to be sent or received from the Zabbix Server 
	:type response: String
	:param hostname_or_id: name or id of the object
	:type hostname_or_id: String
	:param server: Zabbix server
	:type server: ZabbixServer
	
	:raise: :class: `ZabbixRequestError` exception if error
	"""	
	def __init__(self, response, name_or_id, server):			
		self.server = server
		
		# name_or_id is an id: getting the infos from the server
		if type(name_or_id)==int or name_or_id.isdigit():
			logger.debug("HostGroup from id")
			host_results = self.get_data(name_or_id, update = True)
			if not host_results:
				raise ZabbixRequestError("Programmatic error","-1","HostGroup creation impossibile only from id")
		else:
			# name_or_id is a name
			# Check if response is null (Host does not exist)
			name = name_or_id
			if len(response)==0:
				logger.debug("TODO: HostGroup creation")
				# TODO: Create the HostGroup from server and populate attributes (Template does not exists)
			else:
				# Gets data from hostname (HostGroup exists)
				logger.debug("Getting HostGroup info from name")
				self.get_data_from_name(name, update=True)
				
	def dict(self, *args):
		out = []
		for v in args:
			out.append(v)
		return out
			
	def __str__(self):
		return "HostGroup %s" % self.name	
		
	def get_data(self, id, update=False):
		logger.debug("Getting data")
		output = None
		creation_response = _json_constructor("hostgroup.get", self.server.auth, output="extend", filter={"groupid":id})
		response = self.server._request_handler(creation_response)
		# Get the Host from Server and populate attributes
		if len(response['result']) > 0:
			output = response['result'][0]
			if update:
				self.update(output)
		return output

	def update(self, dictionary_info):
		logger.debug("Updating info...")
		if not type(dictionary_info) == dict:
			raise ZabbixRequestError("Programmatic error","-1","Error in function update")
		for (k, v) in dictionary_info.iteritems():
			# TODO: Needs to detects groups and other "classable" items
			if k in classable_types:
				pass
			setattr(self,k,v)

	def get_data_from_name(self, name, update=False):
		logger.debug("Getting data from hostname")
		creation_response = _json_constructor("hostgroup.get", self.server.auth, output="extend", filter={"name":name})
		response = self.server._request_handler(creation_response)
		if update:
			self.update(response['result'][0])
		return response['result']	
		

class Template(object):
	"""
	Template Class
	
	:param response: JSON string to be sent or received from the Zabbix Server 
	:type response: String
	:param hostname_or_id: name or id of the object
	:type hostname_or_id: String
	:param server: Zabbix server
	:type server: ZabbixServer

	:raise: :class: `ZabbixRequestError` exception if error
	"""
	
	def __init__(self, response, name_or_id, server):			
		self.server = server
		
		# name_or_id is an id: getting the infos from the server
		if type(name_or_id)==int or name_or_id.isdigit():
			logger.debug("Template from id")
			host_results = self.get_data(name_or_id, update = True)
			if not host_results:
				raise ZabbixRequestError("Programmatic error","-1","Template creation impossibile only from id")
		else:
			# name_or_id is a name
			# Check if response is null (Host does not exist)
			name = name_or_id
			if len(response)==0:
				logger.debug("TODO: Template creation")
				# TODO: Create the template from server and populate attributes (Template does not exists)
			else:
				# Gets data from hostname (Template exists)
				logger.debug("Getting template info from name")
				self.get_data_from_name(name, update=True)
				
	def dict(self, *args):
		out = []
		for v in args:
			out.append(v)
		return out
			
	def __str__(self):
		return "Template %s" % self.name	
		
	def get_data(self, id, update=False):
		logger.debug("Getting data")
		output = None
		creation_response = _json_constructor("template.get", self.server.auth, output="extend", filter={"hostid":id})
		response = self.server._request_handler(creation_response)
		# Get the Host from Server and populate attributes
		if len(response['result']) > 0:
			output = response['result'][0]
			if update:
				self.update(output)
		return output

	def update(self, dictionary_info):
		logger.debug("Updating info...")
		if not type(dictionary_info) == dict:
			raise ZabbixRequestError("Programmatic error","-1","Error in function update")
		for (k, v) in dictionary_info.iteritems():
			# TODO: Needs to detects groups and other "classable" items
			if k in classable_types:
				pass
			setattr(self,k,v)

	def get_data_from_name(self, name, update=False):
		logger.debug("Getting data from hostname")
		creation_response = _json_constructor("template.get", self.server.auth, output="extend", filter={"host":name})
		response = self.server._request_handler(creation_response)
		if update:
			self.update(response['result'][0])
		return response['result']

class Host(object):
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
		logger.debug("Getting data")
		output = None
		creation_response = _json_constructor("host.get", self.server.auth, output="extend", selectGroups= "extend", filter={"hostid":id})
		response = self.server._request_handler(creation_response)
		# Get the Host from Server and populate attributes
		if len(response['result']) > 0:
			output = response['result'][0]
			if update:
				self.update(output)
		return output

	def update(self, dictionary_info):
		logger.debug("Updating info...")
		if not type(dictionary_info) == dict:
			raise ZabbixRequestError("Programmatic error","-1","Error in function update")
		for (k, v) in dictionary_info.iteritems():
			# TODO: Needs to detects groups and other "classable" items
			if k in classable_types:
				pass
			setattr(self,k,v)

	def get_data_from_hostname(self, hostname, update=False):
		logger.debug("Getting data from hostname")
		creation_response = _json_constructor("host.get", self.server.auth, output="extend", selectGroups= "extend", filter={"host":hostname})
		response = self.server._request_handler(creation_response)
		if update:
			self.update(response['result'][0])
		return response['result']
		
	def get_groups(self):
		if hasattr(self, 'groups'):
			return self.groups
		return None
		
	def __str__(self):
		return "Host %s" % self.name
		
	def __repr__(self):
		return self.__str__()
		
	def __unicode__(self):
		return "Host %s" % self.name