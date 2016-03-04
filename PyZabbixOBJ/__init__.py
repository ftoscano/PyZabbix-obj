from __future__ import unicode_literals
import logging
import requests
import json

rpc_url = "/api_jsonrpc.php"

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
	return p
	

class ZabbixRequestError(Exception):
	def __init__(self, value, code, message):
		self.value = value
		self.code = code
		self.message = message
	def __str__(self):
		return repr("%s , %s - Code: %s"% (self.value, self.message, self.code))	

	
class ZabbixServer(object):
	url = None
	auth = None
	https = False
	headers = {
		"Content-Type": "application/json-rpc"
	}	
			
	def _request_handler(self, request, output = None):
		if self.auth is None and request['method'] != "apiinfo.version" and request['method'] != "user.login":
			raise ZabbixRequestError("LOGIN NOK","-1","User is not logged in")
		response = requests.post(self.api_server, headers=self.headers, data=json.dumps(request)).json()
		if 'error' in response:
			raise ZabbixRequestError(response['error']['data'],response['error']['code'],response['error']['message'])
		return response
	
	def login(self, user, pw):
		if self.auth is not None:
			return True
		json_object = _json_constructor("user.login", None, user=user, password=pw)
		login_response = self._request_handler(json_object)
		self.auth = login_response['result']
	
	def get_version(self):
		json_object = _json_constructor("apiinfo.version", None)
		response = self._request_handler(json_object)
		return response['result']
	
	def __init__(self, server):
		self.api_server = server+rpc_url
		pass
		
	def get_hosts(self, hostnames):
		# Check if hostname is a single hostname (String)
		if type(hostnames) is str:
			hostnames = [hostnames]
		json_object = _json_constructor("host.get", self.auth, output="extend", selectGroups= "extend", 
						filter={"host":hostnames})
		response = self._request_handler(json_object)
		hosts = []
		for results in response['result']:
			hosts.append(Host(results))
		return hosts
		
	def __str__(self):
		return "Server Zabbix %s" % self.url

class HostGroup(ZabbixServer):
	def _request_handler(self, request, output = None):
		super(self.__class__, self)._request_handler(request, output = None)
		
	def __init__(self, response):
		try:
			for (k, v) in response.iteritems():
				setattr(self,k,v)
		except Exception as e:
			raise Exception("Error during hostgroup creation: %s" % e)
		
	def __str__(self):
		return "HostGroup %s" % self.name		

class Host(ZabbixServer):
	def _request_handler(self, request, output = None):
		super(self.__class__, self)._request_handler(request, output = None)
		
	def __init__(self, response):
		try:
			for (k, v) in response.iteritems():
				setattr(self,k,v)
		except Exception as e:
			raise Exception("Error during host creation: %s" % e)
	
	def get_groups(self):
		if hasattr(self, 'groups'):
			return self.groups
		
	def __str__(self):
		return "Host %s" % self.name
		
	def __unicode__(self):
		return "Host %s" % self.name