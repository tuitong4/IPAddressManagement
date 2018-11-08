import logging
import psycopg2
import time
import IPy
import re
import hashlib
import time
import random

from errors import *
from staticparams import *


def md5_timestamp():
	time_t = str(time.time()) + str(random.randint(1, 100))
	time_t = time_t.encode("utf-8")
	return hashlib.new("md5", bytes(time_t)).hexdigest()

class IPAM():
	
	def __init__(self):
		self._logger = logging.getLogger(self.__class__.__name__)


	def is_ipv4(self, ip):
		"""Detect if the given ip is ipv4"""

		try:
			addr = IPy.IP(ip)
		except ValueError:
			return False
		if addr.version() == 4:
			return True
		return False

	def is_ipv6(self, ip):
		"""Detect if the given ip is ipv6"""
		 
		try:
			addr = IPy.IP(ip)
		except ValueError:
			return False
		if addr.version() == 6:
			return True
		return False

	def get_addrfamily(self, ip):
		if self.is_ipv4(ip):
			return 4
		elif self.is_ipv6(ip):
			return 5
		else:
			raise IPAMValueError("Ivalid IP address %s" % ip)

	
	def connect_db(self, host=None, port=5432, database=None, user=None, password=None):
		db_args = {}
		db_args["host"] = host
		db_args["database"] = database
		db_args["user"] = user
		db_args["password"] = password
		db_args["port"] = port

		for key in db_args.copy():
			if db_args[key] is None or db_args == "":
				del(db_args[key])


		#Try to connect database.
		try:
			self._con_pg = psycopg2.connect(**db_args)
			self._curs_pg = self._con_pg.cursor()
		except Exception as e:	
			self._logger.error("%s" % e.args[0])
			raise IPAMDatabaseError("%s" % e.args[0])
		

	def close_db(self):
		  self._curs_pg.close()
		  self._con_pg.close()


	def sql_execute(self, sql, opt=None, callno=0):
		"""Execute query, catch and log errors.
		"""

		try:
			self._curs_pg.execute(sql, opt)
		except psycopg2.InternalError as e:
			self._con_pg.rollback()

			if len(e.split(":") < 2):
				raise IPAMError(e)
			
			code = e.split(":", 1)[0]
			try:
				int(code)
			except:
				raise IPAMError(e)
			
			text = e.splitlines()[0].split(":", 1)[1]
			
			if code == '1200':
				raise IPAMValueError(text)
			
			err_str = "Internal database error: %s" % e
			self._logger.error(err_str)
			raise IPAMError(e)

		except psycopg2.IntegrityError as e:
			self._con_pg.rollback()
			
			# this is a duplicate key error
			if e.pgcode == "23505":
				# figure out which column it is and retrieve the database
				# description for that column
				m = re.match(r'.*"([^"]+)"', e.pgerror)
				if m is None:
					raise IPAMDuplicateError("Objects primary keys already exist")
				cursor = self._con_pg.cursor()
				cursor.execute("""  SELECT
										obj_description(oid)
									FROM pg_class
									WHERE relname = %(relname)s""",
								{ 'relname': m.group(1) })
				
				for desc in cursor:
					column_desc = desc[0]

				if column_desc is None:
					column_desc = '<unknown>'
				# figure out the value for the duplicate value
				column_value = None
				try:
					m = re.match(r'.*=\(([^)]+)\) already exists.', e.pgerror.splitlines()[1])
					if m is not None:
						column_value = m.group(1)
				except:
					pass
				else:
					raise IPAMDuplicateError("Duplicate value for '" +
						column_desc + "', the value '" +

						column_value + "' is already in use.")
				
				raise IPAMDuplicateError("Duplicate value for '" +
					column_desc +"', the value you have inputted is already in use.")
			
			self._logger.exception("Unhandled database IntegrityError: %s" % e )
			raise IPAMError("Unhandled integrity error.")

		except psycopg2.DataError as e:
			self._con_pg.rollback()

			m = re.search('invalid cidr value: "([^"]+)"', e.pgerror)
			if m is not None:
				strict_prefix = IPy.IP(m.group(1), make_net = True)
				err_str = "Invalid prefix (%s); bits set to right of mask. Network address for current mask: %s" % (m.group(1), strict_prefix)
				raise IPAMValueError(err_str)
			
			m = re.search(r'invalid input syntax for(?: type)? (\w+): "([^"]+)"', e.pgerror)

			if m is not None:
				if m.group(1) in ["cidr", "inet"]:
					err_str = "Invalid syntax for prefix (%s)" % m.group(2)
				else:
					err_str = "Invalid syntax for %s (%s)" % (m.group(1), m.group(2))
				raise IPAMValueError(err_str)

			self._logger.exception("Unhandled database DataError:")
			raise IPAMError("Unhandled data error.")

		except psycopg2.Error as e:
			try:
				self._con_pg.rollback()
			except psycopg2.Error:
				pass

			err_str = "Unable to execute query: %s" % e
			self._logger.error(err_str)

			# abort if we've already tried to reconnect
			if callno > 0:
				self._logger.error(err_str)
				raise IPAMError(err_str)

			# reconnect to database and retry query
			self._logger.info("Reconnecting to database...")
			self.connect_db()

			return self.sql_execute(sql, opt, callno + 1)

		except psycopg2.Warning as warn:
			self._logger.warning(warn)  

	def sql_commit(self):
		self._con_pg.commit()
		self._logger.info("Commited execution.")

	def sql_rollback(self):
		self._con_pg.rollback()
		self._logger.info("Rollback execution.")

	def sql_expand_insert(self, spec, key_prefix = '', col_prefix = ''):
		""" Expand a dict so it fits in a INSERT clause
		"""
		col = list(spec)
		sql = '('
		sql += ', '.join(col_prefix + key for key in col)
		sql += ') VALUES ('
		sql += ', '.join('%(' + key_prefix + key + ')s' for key in col)
		sql += ')'
		params = {}
		for key in spec:
			params[key_prefix + key] = spec[key]

		return sql, params


	def sql_expand_update(self, spec, key_prefix = '', col_prefix = ''):
		""" Expand a dict so it fits in a INSERT clause
		"""
		sql = ', '.join(col_prefix + key + ' = %(' + key_prefix + key + ')s' for key in spec)
		params = {}
		for key in spec:
			params[key_prefix + key] = spec[key]

		return sql, params


	def sql_expand_where(self, spec, key_prefix = '', col_prefix = ''):
		""" Expand a dict so it fits in a WHERE clause
			Logical operator is AND.
		"""

		sql = ' AND '.join(col_prefix + key + 
			( ' IS ' if spec[key] is None else ' = ' ) +
			'%(' + key_prefix + key + ')s' for key in spec)
		params = {}
		for key in spec:
			params[key_prefix + key] = spec[key]

		return sql, params


	def _add_prefix(self, attr):
		#
		# Insert a prefix into db table
		#
		insert, params = self.sql_expand_insert(attr)
		sql = "INSERT INTO ip_net_assign %s" % insert

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)


	def record_history(self):
		pass

	def add_root_prefix(self, prefix=None, addrspace=None, vrf="global", 
						provider=None, casttype=UNICAST, nettype=None):
		#
		# Add a root prefix into db table
		#
		if addrspace is None:
			raise IPAMValueError("Addrspace is expected but get 'None'.")

		if prefix is None:
			raise IPAMValueError("Prefix is expected but get 'None'.")
		#init sql parameter
		attr = {}
		attr ["prefix"] = prefix
		attr ["addrspace"] = addrspace
		attr ["vrf"] = vrf
		if provider is not None:
			attr ["provider"] = provider

		attr ["casttype"] = casttype
		if nettype is not None:
			attr ["nettype"] = nettype

		attr["addrfamily"] = self.get_addrfamily(prefix)

		attr["root"] = True
		
		attr["recordid"] = md5_timestamp()
		attr["updatetime"] = time.time()

		self._add_prefix(attr)
		self.record_history()
        
		self.sql_commit()
		return attr["recordid"]





