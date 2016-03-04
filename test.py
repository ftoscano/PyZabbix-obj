import PyZabbixOBJ
z = PyZabbixOBJ.ZabbixServer("http://localhost/zabbix")
z.login("Admin","zabbix")
hosts = z.get_hosts("PESCHIERA_BORROMEO_SECURITY_DR",)
print hosts[0].groups
