#!/usr/bin/env python
# encoding: utf-8
"""
http.py

Created by Thomas Mangin on 2011-12-02.
Copyright (c) 2011 Exa Networks. All rights reserved.
"""

from exaproxy.util.logger import logger
from exaproxy.configuration import configuration
from exaproxy.network.functions import isip

class HostMismatch(Exception):
	pass

class Header(dict):
	def __init__(self, header,remote_ip):	
		self.order = []

		logger.info('header','parsing %s' % str(header))

		try:
			request, remaining = header.split('\r\n',1)

			method, fullpath, version = request.split()
			method = method.upper()
			version = version.split('/')[-1]

			if '://' in fullpath:
				x, b = fullpath.split('://', 1)
				if '/' not in x:
					fullpath = b
					protocol = x
				else:
					protocol = 'http'
			else:
				protocol = 'http'


			if '/' in fullpath:
				fullpath, path = fullpath.split('/', 1)
				path = '/' + path
			else:
				path = '/'


			if ':' in fullpath:
				host, port = fullpath.split(':', 1)
				if not port.isdigit():
					host = None
					port = None
					path = None
				else:
					port = int(port)
			else:
				# fullpath will be '' if GET / HTTP/1.x is used
				host = fullpath
				port = None

			key = None
			data = None

			for line in remaining.split('\r\n'):
				if not line:
					break

				if line[0].isspace():
					if key:
						data += line.lstrip()
						continue
					else:
						raise Exception, 'Whitespace before headers'

				if ':' not in line:
					raise Exception, 'Malformed headers'
				
				if key:
					self.order.append(key)
					self[key] = data

				key,value = line.split(':',1)
				key = key.strip().lower()
				data = line
				if not key:
					raise Exception, 'Malformed headers'

				if key == 'host' and not host:
					host = value.strip().lower()

			# buffered value holds the complete data for the current key
			self.order.append(key)
			self[key] = data

			self['x-proxy-version'] = "X-Proxy-Version: %s version %s" % (configuration.NAME, configuration.VERSION)

			if method == 'CONNECT':
				self.order.append('host')
				if 'host' not in self:
					self['host'] = 'Host: ' + host

			if method != 'CONNECT':
				requested_host = self.get('host', ':').split(':', 1)[1].strip()
				if host is not None and requested_host != host:
					raise HostMismatch, 'make up your mind: %s - %s' % (requested_host, host)

				host = requested_host

			if configuration.XFF:
				client = self.get('x-forwarded-for', ':%s' % remote_ip).split(':', 1)[1].split(',')[-1].strip()
				if not isip(client):
					logger.info('header', 'Invalid address in X-Forwarded-For: %s' % client)
					client = remote_ip
			else:
				client = remote_ip

			url = host + ((':'+str(port)) if port is not None else '') + path
			port = port if port is not None else 80

			url_noport = host + path
		except KeyboardInterrupt:
			raise
		except Exception, e:
			logger.error('header','could not parse header %s %s' % (type(e),str(e)))
			method, path, version = None, None, None
			protocol, host, port, url = None, None, None, None
			url_noport = None
			client, request = None, None

		self.request = request
		self.method = method
		self.path = path
		self.version = version
		self.protocol = protocol
		self.host = host
		self.port = port
		self.url = url
		self.url_noport = url_noport
		self.client = client

	def __setitem__ (self,key,value):
		if not key in self.order:
			self.order.append(key)
		dict.__setitem__ (self,key,value)

	def pop(self, key):
		res = dict.pop(self, key)
		self.order.remove(key)
		return res

	def redirect(self, host, path):
		self.host = host if host is not None else self.host
		self.path = path if path is not None else self.path

		# XXX: need to handle port switch
		if path is not None:
			self.request = self.method + ' ' + path + 'HTTP/1.1'

		if host is not None:
			self['host'] = 'Host: ' + host

	def isValid(self):
		return self.method is not None and self.host is not None and self.path is not None

	def toString(self, linesep='\r\n'):
		request = str(self.method) + ' ' + str(self.path) + ' HTTP/1.1'
		return request + linesep + linesep.join(self[key] for key in self.order) + linesep + linesep
