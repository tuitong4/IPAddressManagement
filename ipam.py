import logging
import psycopg2
import IPy
import re
from errors import *
import collections


#
# Specifier describes the relationship bettwen geiven data and database's data structure.
#

#databse table ipaddress specfier.
prefix_spec = {
	"addrspace": {
		"column": "addrspace",
		"autofill": False
	},
	"vrf": {
		"column": "vrf",
		"autofill": False
	},
	"appretain": {
		"column": "appretain",
		"autofill": False
	},
	"location": {
		"column": "location",
		"autofill": False
	},
	"expires": {
		"column": "expires",
		"autofill": False
	},
	"industry": {
		"column": "industry",
		"autofill": False
	},
	"provider": {
		"column": "provider",
		"autofill": False
	},
	"customer": {
		"column": "customer",
		"autofill": False
	},
	"assignstatus": {
		"column": "assignstatus",
		"autofill": False
	},
	"description": {
		"column": "description",
		"autofill": False
	},
	"comment": {
		"column": "comment",
		"autofill": False
	},
	"tags": {
		"column": "tags",
		"autofill": False
	},
	"application": {
		"column": "application",
		"autofill": False
	},
	"addrfamily": {
		"column": "addrfamily",
		"autofill": False
	},
	"casttype": {
		"column": "casttype",
		"autofill": False
	},
	"share": {
		"column": "share",
		"autofill": False
	},
	"usagetype": {
		"column": "usagetype",
		"autofill": False
	},
	"prefix": {
		"column": "prefix",
		"autofill": False
	},
	"prefixid": {
		"column": "prefixid",
		"autofill": True
	},
	"parentprefix": {
		"column": "parentprefix",
		"autofill": False
	}
}


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


	def exec_sql(self, sql, opt=None, callno=0):
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
				column_desc = '<unknown>'
				for desc in cursor:
					column_desc = desc[0]

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

			m = re.search('invalid input syntax for(?: type)? (\w+): "([^"]+)"', e.pgerror)
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

			return self.exec_sql(sql, opt, callno + 1)

		except psycopg2.Warning as warn:
			self._logger.warning(warn)  



	def add_new_prefix(self, attr):

		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))
		
				

if __name__ == "__main__":
	ipam = IPAM()
	ipam.connect_db(host="11.3.245.227", port=54321, database="postgres", user="postgres", password="123456")
	ipam.exec_sql("select * from ipaddres")
	for item in ipam._curs_pg:
		print(item)

	{"orgin_name":{ "column":"db_column",
					"ref" : {"table":"table", "column":""},
					"auto_fill" : True,

					}		
	}