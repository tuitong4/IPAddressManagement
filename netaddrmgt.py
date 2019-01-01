import logging
import psycopg2
import time
import datetime
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

	def _update_prefix(self, attr, prefix):
		#
		# update a prefix' attribute
		#
		update, params = self.sql_expand_update(attr)
		sql = "UPDATE ip_net_assign SET %s WHERE prefix = '%s'::INET" % (update, prefix)

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)


	def exist_prefix(self, prefix, vrf="global", strict=False):
		#
		# strict is comparing prefixs exactly.
		#
		if not strict:
			sql = """SELECT count(*) FROM ip_net_assign WHERE '%s'::INET >>= prefix AND vrf = '%s'""" % (prefix, vrf)
		else:
			sql = """SELECT count(*) FROM ip_net_assign WHERE '%s'::INET = prefix AND vrf = '%s'""" % (prefix, vrf)

		self._logger.info("Execute %s." % sql)
		self.sql_execute(sql)
		if self._curs_pg.fetchone()[0] > 0:
			return True
		else:
			return False 


	def verify_attribute(self, orgin_attr, required_attr):
		#
		#orgin_attr is a dict.
		#required_attr is a list.
		#

		for key in required_attr:
			try :
				if orgin_attr[key] is False:
					continue
				if not orgin_attr[key]:
					raise IPAMValueError("'%s' need a pernament value rather than '' or None." % key)
			except KeyError:
				raise IPAMValueError("Missing atrribute '%s'." % key)

	def omitte_attribute(self, orgin_attr, omitted_attr):
		#
		# orgin_attr is a dict.
		# omitted_attr is a list or tuple.
		#

		for key in omitted_attr:
			if key in orgin_attr:
				orgin_attr.pop(key)

	def empty_attribute(self, orgin_attr, empty_attr):
		#
		# orgin_attr is a dict.
		# empty_attr is a list or tuple.
		#
		for key in empty_attr:
			if key in orgin_attr:
				orgin_attr[key] = None

	def emptiable_attribute(self, orgin_attr, emptiable_attribute):
		#
		# orgin_attr is a dict.
		# emptiable_attribute is a list or tuple.
		#

		for key in emptiable_attribute:
			if key not in orgin_attr:
				orgin_attr[key] = None

	def inherit_attribute(self, orgin_attr, herit_attr, herited_attr):
		#
		# orgin_attr is a dict.
		# herit_attr is a list or tuple.
		# herited_attr is dict. which be inherited.
		#

		for key in herit_attr:
			if key in herited_attr:
				orgin_attr[key] = herited_attr.pop(key)
			else:
				raise IPAMValueError("The key '%s' is not in herit attribute.")

	def inheritable_attribute(self, orgin_attr, herit_attr, herited_attr):
		#
		# orgin_attr is a dict.
		# herit_attr is a list or tuple.
		# herited_attr is dict. which be inherited.
		#
		for key in herit_attr:
			if not orgin_attr[key]:
				if key in herited_attr:
					orgin_attr[key] = herited_attr.pop(key)
				else:
					raise IPAMValueError("The key '%s' is not in herit attribute.")

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
		attr["updatetime"] = datetime.datetime.now()

		self._add_prefix(attr)

		self.sql_commit()
		return attr["recordid"]

	def assign_prefix(self, attr, refer_prefix):
		#
		# attr is the attribute of prefix.
		#
		
		sub_prefix = attr["prefix"]
		vrf = attr["vrf"]
		if not sub_prefix:
			raise IPAMValueError("Prefix should be specified!")

		if not vrf:
			raise IPAMValueError("VRF is requried, but get 'None'!")
		
		if IPy.IP(sub_prefix) not in IPy.IP(refer_prefix):
			raise IPAMValueError("Prefix %s is not a sub prefix of %s." % (sub_prefix, refer_prefix))

		sql = """SELECT * FROM ip_net_assign WHERE '%s'::INET = prefix AND vrf = '%s'""" % (refer_prefix, vrf)
		self.sql_execute("SELECT row_to_json(r) FROM (%s) r" % sql)
		
		refer_attr = self._curs_pg.fetchone()[0]

		if IPy.IP(sub_prefix) == IPy.IP(refer_prefix) and refer_prefix["root"]:
			attr["root"] = True
			self.update_prefix(attr, refer_attr, status_opt=True)
			return
		else:
			attr["root"] = False


		if self.exist_prefix(sub_prefix, attr["vrf"]):
			raise IPAMDuplicateError("Prefix or subprefix '%s' is already exists." % sub_prefix)

		#Case 1
		if attr["assignstatus"] == RESERVED:
			required_attr = ("reservednode",)
			omitted_attr  = ("assignednode", "expires", "customer")
			inherit_attr  = ("addrspace", "vrf", "provider", "addrfamily", "nettype")

			self.verify_attribute(attr, required_attr)
			self.omitte_attribute(attr, omitted_attr)
			self.inherit_attribute(attr, inherit_attr, refer_attr)

		#Case 2
		elif attr["assignstatus"] == ASSIGNED:
			required_attr = ("assignednode", "customer", "application", "casttype", "shared", "usagetype")
			inherit_attr  = ("addrspace", "vrf", "provider", "addrfamily", "nettype")
			inheritable_attr = ("reservednode", "industry")

			self.verify_attribute(attr, required_attr)
			self.inherit_attribute(attr, inherit_attr, refer_attr)
			self.inheritable_attribute(attr, inheritable_attr, refer_attr)

			if not attr["industry"] :
				raise IPAMValueError("You should specific the industry when assign a prefix to users!")

			attr["leaf"] = True

		#Case 3
		elif attr["assignstatus"] == IDLE:
			omitted_attr  = ("reservednode", "assignednode", "expires", "industry", "customer", "application", "casttype",\
							"shared", "usagetype")
			inherit_attr  = ("addrspace", "vrf", "provider", "description", "comments", "tags", "addrfamily", "nettype")
			
			self.omitte_attribute(attr, omitted_attr)
			self.inherit_attribute(attr, inherit_attr, refer_attr)

			attr["leaf"] = False

		#Case 4
		elif attr["assignstatus"] == QUARANTINE:
			omitted_attr  = ("reservednode", "assignednode", "expires", "industry", "customer", "application", "casttype",\
							"shared", "usagetype")
			inherit_attr  = ("addrspace", "vrf", "provider", "description", "comments", "tags", "addrfamily", "nettype")
			
			self.omitte_attribute(attr, omitted_attr)
			self.inherit_attribute(attr, inherit_attr, refer_attr)

			attr["leaf"] = False
		else:
			raise IPAMValueError("Unsupported status '%s'." % attr["assignstatus"])

		attr["recordid"] = md5_timestamp()
		attr["updatetime"] = datetime.datetime.now()
		attr["originalid"] = None

		self._add_prefix(attr)

		return

	def update_prefix(self, attr, old_attr=None, status_opt=True):
		# 
		# status_opt = True, means update the assignstauts of the prefix.
		# status_opt = Fasle, means update other attributes of the prefix except assignstauts.
		#
		prefix = attr["prefix"]
		vrf = attr["vrf"]

		if not status_opt:
			updateble_attr = ("expires", "industry", "provider", "customer", "description", "comments",\
							   "tags", "application", "casttype", "shared", "usagetype")
			_update_attr = {}
			for key in updateble_attr:
				if key in attr:
					_update_attr[key] = attr

			if not attr:
				raise IPAMValueError("Nothing to update!")
			
			self._update_prefix(attr, prefix)
			return


		if old_attr is None:
			sql = """SELECT * FROM ip_net_assign WHERE '%s'::INET = prefix AND vrf = '%s'""" % (prefix, vrf)
			self.sql_execute("SELECT row_to_json(r) FROM (%s) r" % sql)
			resp = self._curs_pg.fetchone()
			if resp:
				old_attr = resp[0]
			else:
				raise IPAMValueError("No prefix whith VRF '%s'!" % vrf )
			
		
		old_status = old_attr["assignstatus"]
		new_status = attr["assignstatus"]
		
		#Case 1: Assigned --> Reserved
		if old_status == ASSIGNED and new_status == RESERVED:
			omitted_attr = ("prefix", "vrf", "addrspace", "provider", "addrfamily", "nettype")

			self.sql_execute("SELECT row_to_json(r) FROM (SELECT * FROM ip_net_assign_log where idx = '%s') r" % old_attr["originalid"])
			orgin_attr = self._curs_pg.fetchone()[0]
			#TODO: check orgin_attr when it is {}.

			inherit_attr = ("reservednode", "industry", "description", "comments", "tags", "application", "casttype", "shared", "usagetype")
			empty_attr = ("assignednode", "expires", "customer")

			self.omitte_attribute(attr, omitted_attr)
			self.inherit_attribute(attr, inherit_attr, orgin_attr)
			self.empty_attribute(attr, empty_attr)
			attr["leaf"] = True

		#Case 2: Reserved --> Assigned
		elif old_status == RESERVED and new_status == ASSIGNED:
			omitted_attr = ("prefix", "vrf", "addrspace", "reservednode", "provider", "addrfamily", "nettype")
			required_attr = ("assignednode", "industry", "application", "casttype", "shared", "usagetype")
			
			self.omitte_attribute(attr, omitted_attr)
			self.verify_attribute(attr, required_attr)
			attr["leaf"] = True

		#Case 3: Reserved --> Reserved
		elif old_status == RESERVED and new_status == RESERVED:
			omitted_attr = ("prefix", "vrf", "addrspace", "assignednode", "expires", "provider", "customer", "addrfamily", "nettype")
			required_attr = ("reservednode",)
			emptiable_attr = ("industry", "description", "comments", "tags", "application", "casttype", "shared", "usagetype")

			self.omitte_attribute(attr, omitted_attr)
			self.verify_attribute(attr, required_attr)
			self.emptiable_attribute(attr, emptiable_attr)

			attr["leaf"] = True

		#Case 4: Reserved --> Idle
		elif  old_status == RESERVED and new_status == IDLE:
			omitted_attr = ("prefix", "vrf", "addrspace", "reservednode", "expires", "provider", "customer", "addrfamily", "nettype")
			empty_attr = ("assignednode", "industry", "description", "comments", "tags", "application", "casttype", "shared", "usagetype")
			
			self.omitte_attribute(attr, omitted_attr)
			self.empty_attribute(attr, empty_attr)

			attr["leaf"] = False

		#Case 5: Reserved --> Quarantine
		elif  old_status == RESERVED and new_status == QUARANTINE:
			omitted_attr = ("prefix", "vrf", "addrspace", "reservednode", "expires", "provider", "customer", "addrfamily", "nettype")
			empty_attr = ("assignednode", "industry", "description", "comments", "tags", "application", "casttype", "shared", "usagetype")
			
			self.omitte_attribute(attr, omitted_attr)
			self.empty_attribute(attr, empty_attr)

			attr["leaf"] = False

		#Case 6: Idle --> Assigned
		elif old_status == IDLE and new_status == ASSIGNED:
			omitted_attr = ("prefix", "vrf", "addrspace",  "provider", "addrfamily", "nettype")
			required_attr = ("assignednode", "industry", "customer", "application", "casttype", "shared", "usagetype")
			emptiable_attr = ("description", "comments", "tags")
			
			self.omitte_attribute(attr, omitted_attr)
			self.emptiable_attribute(attr, emptiable_attr)
			self.verify_attribute(attr, required_attr)

			#If reservednode not exisits or reservednode is None, Use the value of assignednode.
			if "reservednode" not in attr or not attr["reservednode"]:
				 attr["reservednode"] = attr["assignednode"]

			attr["leaf"] = True

		#Case 7: Idle --> Reserved
		elif old_status == IDLE and new_status == RESERVED:
			omitted_attr = ("prefix", "vrf", "addrspace", "assignednode", "provider", "addrfamily", "nettype")
			required_attr = ("reservednode",)
			emptiable_attr = ("description", "comments", "tags")
			
			self.omitte_attribute(attr, omitted_attr)
			self.emptiable_attribute(attr, emptiable_attr)
			self.verify_attribute(attr, required_attr)

			attr["leaf"] = True

		#Case 8: Idle --> Quarantine
		elif old_status == IDLE and new_status == QUARANTINE:
			omitted_attr = ("prefix", "addrspace", "vrf", "reservednode", "assignednode", \
			 "expires", "industry", "provider", "customer", "description", \
			  "comments", "tags", "application", "addrfamily", "casttype", "nettype", "shared", \
			   "usagetype", "leaf", "root")

			self.omitte_attribute(attr, omitted_attr)
		
		#Case 9: Quarantine --> Idle
		elif old_status == QUARANTINE and new_status == IDLE:
			omitted_attr = ("prefix", "addrspace", "vrf", "reservednode", "assignednode", \
			 "expires", "industry", "provider", "customer", "description", \
			  "comments", "tags", "application", "addrfamily", "casttype", "nettype", "shared", \
			   "usagetype", "leaf", "root")

			self.omitte_attribute(attr, omitted_attr)

		#case 10: Quarantine -->Assigned
		elif old_status == QUARANTINE and new_status == ASSIGNED:
			omitted_attr = ("prefix", "vrf", "addrspace",  "provider", "addrfamily", "nettype")
			required_attr = ("assignednode", "industry", "customer", "application", "casttype", "shared", "usagetype")
			emptiable_attr = ("description", "comments", "tags")
			
			self.omitte_attribute(attr, omitted_attr)
			self.emptiable_attribute(attr, emptiable_attr)
			self.verify_attribute(attr, required_attr)

			#If reservednode not exisits or reservednode is None, Use the value of assignednode.
			if "reservednode" not in attr or not attr["reservednode"]:
				 attr["reservednode"] = attr["assignednode"]

			attr["leaf"] = True


		#Case 11: Quarantine --> Reserved
		elif old_status == QUARANTINE and new_status == RESERVED:
			omitted_attr = ("vrf", "addrspace", "assignednode", "provider", "addrfamily", "nettype")
			required_attr = ("reservednode",)
			emptiable_attr = ("description", "comments", "tags")
			
			self.omitte_attribute(attr, omitted_attr)
			self.emptiable_attribute(attr, emptiable_attr)
			self.verify_attribute(attr, required_attr)

			attr["leaf"] = True

		else:
			raise IPAMValueError("Unsupported Change %s to %s!" % (old_status, new_status))

		attr["root"] = old_attr["root"]
		attr["recordid"] = md5_timestamp()
		attr["updatetime"] = datetime.datetime.now()
		attr["originalid"] = old_attr["recordid"]

		self._update_prefix(attr, prefix)

		return


	def _add_porvider(self, attr):

		required_attr = ("fullname", "shortname")
		self.verify_attribute(attr, required_attr)

		insert, params = self.sql_expand_insert(attr)
		sql = """INSERT INTO ip_net_provider %s RETURNING id""" % insert

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)
		return self._curs_pg.fetchone()[0]


	def add_porvider(self, attr):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Invalid input attribute type %s." % type(attr))

		try:
			record_id = self._add_porvider(attr)
		except IPAMDuplicateError:
			raise("Provider '%s' is already exisits!" % attr["shortname"])

		return record_id

	def _update_provider(self, attr):
		update, params = self.sql_expand_update(attr)
		sql = """UPDATE ip_net_provider SET %s RETURNING id""" % update

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)
		record_id = next(self._curs_pg)[0]

		return record_id

	def update_provider(self, attr, old_provider_name=None):
		updateble_attr = ("fullname", "shortname", "description")
		_update_attr = {}
		for key in updateble_attr:
			if key in attr:
				_update_attr[key] = attr

		if not attr:
			raise IPAMValueError("Nothing to update!")

		try:
			self._update_provider(attr)

			#Update all relation provider shortname of table ip_net_assign.
			if not old_provider_name:
				sql = "UPDATE ip_net_assign SET porvider = '%s' where provider = '%s'" % (attr["shortname"], old_provider_name)
				self.sql_execute(sql)
		except Exception as e:
			raise(e)	
		
	def add_node(self, attr):
		required_attr = ("region", "datacenter", "pod", "rack", "device")
		for key in required_attr:
			if key not in attr:
				attr[key] = None
		
		sql = "SELECT update_ip_net_node(%s, %s, %s, %s, %s, %s, %s, %s);"
		params = (attr["region"], attr["datacenter"], attr["pod"], attr["rack"], attr["device"], 'insert', None)

		self.sql_execute(sql, params)
		return self._curs_pg.fetchone()[0]

	def update_node(self, attr):
		required_attr = ("region", "datacenter", "pod", "rack", "device", "nodeidx")
		for key in required_attr:
			if key not in attr:
				attr[key] = None
		if not attr["nodeidx"] :
			raise IPAMValueError("The oringial node idx should be specified!")

		sql = "SELECT update_ip_net_node(%s, %s, %s, %s, %s, %s, %s, %s);"
		params = (attr["region"], attr["datacenter"], attr["pod"], attr["rack"], attr["device"], 'update', attr["nodeidx"])

		self.sql_execute(sql, params)
		return self._curs_pg.fetchone()[0]

	def delete_node(self, nodeidx=None):
		if not nodeidx :
			raise IPAMValueError("The oringial node idx should be specified!")

		sql = "SELECT update_ip_net_node(NULL, NULL, NULL, NULL, NULL, NULL, %s, %s);"
		params = ("delete", nodeidx)

		self.sql_execute(sql, params)
		resp_code = self._curs_pg.fetchone()[0]
		
		if resp_code == -2:
			raise IPAMUnupdateValueError("Could not delete the node for it's in use.")

		return resp_code

	def add_note(self, note):
		if note is None or note == "":
			raise IPAMValueError("Note value must not be '' or None.")

		attr = {"note":note}
		insert, params = self.sql_expand_insert(attr)
		sql = "INSERT INTO ip_net_note %s RETURNING id" % insert
		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)

		record_id = next(self._curs_pg)[0]

		return record_id

	def update_note(self, note_idx, new_note):
		if not note_idx:
			raise IPAMValueError("The oringial note index should be specified!")

		if new_note is None or new_note == "":
			raise IPAMValueError("Note value must not be '' or None.")

		#TODO: 处理字符串带有特殊字符的问题，以及SQL注入。
		sql = "UPDATE ip_net_note SET note = '%s' where idx = '%s'" % (new_note, note_idx)
		self._logger.info("Execute: SQL:%s." % sql)
		self.sql_execute(sql)

		return note_idx		

	def delete_note(self, note_idx):
		if not note_idx:
			raise IPAMValueError("The oringial note index should be specified!")

		sql = "SELECT count(*) from ip_net_assign where description = '%s' or comments = '%s' or tags = '%s'" % (note_idx, note_idx, note_idx)
		self._logger.info("Execute: SQL:%s." % sql)
		self.sql_execute(sql)
		count = next(self._curs_pg)[0]
		if count > 0:
			raise IPAMUnupdateValueError("Could not delete the note for it's in use.")

		sql_delete = "DELETE FROM ip_net_note where note_idx = '%s'" % note_idx
		self.sql_execute(sql)
		return note_idx		


if __name__ == "__main__":
	ipam = IPAM()
	ipam.connect_db(host="11.3.245.227", port=443, database="postgres", user="postgres", password="123456")

	attr = {
    "prefix": "114.114.4.0/24",
    "addrspace": 1,
    "vrf": "global",
    "reservednode": 11,
    "assignednode": 12,
    "expires": None,
    "assignstatus": ASSIGNED,
    "description": 1,
    "comments": None,
    "tags": 12,
    "application": 3,
    "casttype": UNICAST,
    "nettype": COMMON,
    "shared": True,
    "usagetype": SERVERMANAGENTADDRESS,
	"customer" : 1,
	"industry" : JDCOM,
	}
	try:
		ipam.update_prefix(attr)
		ipam.close_db()
	except Exception as e:
		print(e)

	finally:	
		ipam.close_db()