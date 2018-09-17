import logging
import psycopg2
import IPy
import re
from errors import *
from staticparams import *



#
# Specifier describes the relationship bettwen geiven data and database's data structure.
#

#databse table ip_net_assign specfier.
prefix_spec = {
	"id": {
		"column": "id",
		"autofill": True
	},
	"prefix": {
		"column": "prefix",
		"autofill": False
	},
	"addrspace": {
		"column": "addrspace",
		"autofill": False
	},
	"vrf": {
		"column": "vrf",
		"autofill": False
	},
	"reservednode": {
		"column": "reservednode",
		"autofill": False
	},
	"assignednode": {
		"column": "assignednode",
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
	"nettype": {
		"column": "nettype",
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
	"leaf": {
		"column": "leaf",
		"autofill": False
	},
}

#databse table ip_net_provider specfier.
provider_spec =	{
	"id": {
		"column": "id",
		"autofill": True
	},
	"fullname": {
		"column": "fullname",
		"autofill": False
	},
	"name": {
		"column": "name",
		"autofill": False
	},
	"description": {
		"column": "description",
		"autofill": False
	},
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

	@staticmethod
	def verify_attribute(input_attr, required_attr):
		#
		#input_attr, refer_attr is a dict.
		#required_attr is a list.
		#
		
		overlap_attr = set(input_attr.keys()) & set(tuple(required_attr))

		if len(overlap_attr) < len(required_attr):
			raise IPAMValueError("Input attribute misses some paramters.")
		
	@staticmethod
	def adapt_attribute(input_attr, refer_attr):
		#Fit input_attr to refer_attr, return a new fitted attribute.
		#
		#input_attr is a dict like {"attr_name":"attr_value"}.
		#refer_attr is a specifier that decribes the relationship bettwen input_attr
		#and the databse data struct. It is like {"attr_name": {"column":"column_name",
		#  "other_key":"other_val"}}.
		#

		attr = {}
		input_keys = list(input_attr.keys())
		for key, val in refer_attr.items():
			if key in input_keys:
				attr[val["column"]] = input_attr.get(key)

		return attr


	def exist_prefix(self, prefix, vrf="global"):
		sql = """SELECT count(id) FROM ip_net_assign WHERE '%s'::INET <<= prefix AND vrf = '%s'""" % (prefix, vrf)

		self._logger.info("Execute %s." %sql)
		self.sql_execute(sql)
		if self._curs_pg.fetchone()[0] > 0:
			return True
		else:
			return False 


	def add_prefix(self, attr):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))
		
		if "addrspace" not in attr:
			raise IPAMValueError("Input parameter miss the 'addrspace' attribute.")

		addrspace = attr["addrspace"]
		#For internet address
		if addrspace == 1:
			required_attr = [
				"prefix",
				"reservednode",
				"provider",
				"casttype",
				"nettype",]

		#For intranet address
		elif addrspace == 2:
			required_attr = ["prefix"]

		else:
			raise IPAMValueError("Address Space expects but get None!")

		self.verify_attribute(attr, required_attr)

		attr["addrfamily"] = self.get_addrfamily(attr["prefix"])
		
		insert, params = self.sql_expand_insert(attr)
		sql = "INSERT INTO ip_net_assign %s RETURNING id" % insert

		if self.exist_prefix(attr["prefix"]):
			raise IPAMDuplicateError("Prefix '%s' is already exists." %attr["prefix"] )

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)
		record_id = next(self._curs_pg)[0]

		self.sql_commit()

		return record_id


	def get_prefix(self, attr, wrap=False):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))

		where, params = self.sql_expand_where(attr)

		sql = "SELECT * FROM ip_net_assign WHERE " + where
		self.sql_execute(sql, params)

		resp = self._curs_pg.fetchall()
		if resp is None:
			return None
		if wrap:
			table_column_name = [
				"id",
				"prefix",
				"addrspace",
				"vrf",
				"reservednode",
				"assignednode",
				"expires",
				"industry",
				"provider",
				"customer",
				"assignstatus",
				"description",
				"comment",
				"tags",
				"application",
				"addrfamily",
				"casttype",
				"nettype",
				"share",
				"usagetype",
				"leaf"]
			records = []
			for item in resp:
				record = {}
				for idx, col in enumerate(table_column_name):
					record[col] = item[idx]

				records.append(record)

			return records
		return resp
		

	def assign_prefix(self, attr, refer_prefix=None):
		# --Prameters--
		# attr is sub prefix's args.
		# refer_prefix is the parent prefix of sub prefix.
		# 
		# --Assignment--
		# If attr["reservednode"] is not offered, use refer_prefix's instead.
		# If attr["assignstatus"] is 'Assigned', attr["assignednode"] must be offered.
		# Check if given prefix is a sub prefix of refer_prefix  befor assignment.
		# 
		if refer_prefix is None:
			raise IPAMInvalidValueTypeError("refer_prefix expects a ip prefix string but get None type.")

		sub_prefix = attr["prefix"]

		if IPy.IP(sub_prefix) not in IPy.IP(refer_prefix):
			raise IPAMValueError("Prefix %s is not a subprefix of %s." % (sub_prefix, refer_prefix))

		if attr.get("vrf") is None:
			attr["vrf"] = "global"
		
		refer_attr = self.get_prefix(attr={"prefix":refer_prefix, "vrf":attr["vrf"]}, wrap=True)[0]
		
		if refer_attr["assignstatus"] == ASSIGNED:
			raise IPAMValueError("Prefix %s is already assigned." % sub_prefix)
		
		if attr.get("reservednode") == None:
			attr["reservednode"] = refer_attr["reservednode"]

		fix_attr = ["addrspace", "vrf", "addrfamily", "nettype", "provider"]
		for _attr in fix_attr:
			attr[_attr] = refer_attr[_attr]

		
		if attr["assignstatus"] == ASSIGNED:
			required_attr = ["prefix", "customer", "application"]
			attr["leaf"] = True
			self.verify_attribute(attr, required_attr)
			
			insert, params = self.sql_expand_insert(attr)
			sql = "INSERT INTO ip_net_assign %s RETURNING id" % insert
			self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
			self.sql_execute(sql, params)

			record_id = next(self._curs_pg)[0]
			self.sql_commit()
			
			return record_id

		if attr["assignstatus"] == RESERVED:
			attr["leaf"] = False

			#For internet address
			if attr["addrspace"] == INTERNET:
				required_attr = [
					"prefix",
					"reservednode",
					"provider",
					"casttype",
					"nettype",]

			#For intranet address
			elif attr["addrspace"] == INTRANET:
				required_attr = ["prefix"]

			self.verify_attribute(attr, required_attr)
			
			insert, params = self.sql_expand_insert(attr)
			sql = "INSERT INTO ip_net_assign %s RETURNING id" % insert
			self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
			self.sql_execute(sql, params)

			record_id = next(self._curs_pg)[0]
			self.sql_commit()
			
			return record_id

		if attr["assignstatus"] == QUARANTINE:
			attr["leaf"] = True
			
			#For internet address
			if attr["addrspace"] == INTERNET:
				required_attr = [
					"prefix",
					"reservednode",
					"provider",
					"casttype",
					"nettype",]

			#For intranet address
			elif attr["addrspace"] == INTRANET:
				required_attr = ["prefix"]

			self.verify_attribute(attr, required_attr)
			
			insert, params = self.sql_expand_insert(attr)
			sql = "INSERT INTO ip_net_assign %s RETURNING id" % insert
			self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
			self.sql_execute(sql, params)

			record_id = next(self._curs_pg)[0]
			self.sql_commit()
			
			return record_id	


	def update_prefix(self, attr):
		pass

	def exist_provider(self, provider_name):
		sql = """SELECT count(id) FROM ip_net_provider WHERE name = '%s'""" % provider_name

		self._logger.info("Execute %s." %sql)
		self.sql_execute(sql)
		if self._curs_pg.fetchone()[0] > 0:
			return True
		else:
			return False 


	def add_porvider(self, attr):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))

		required_attr = ["fullname", "name"]
		self.verify_attribute(attr, required_attr)

		insert, params = self.sql_expand_insert(attr)
		sql = """INSERT INTO ip_net_provider %s RETURNING id""" % insert

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)
		record_id = next(self._curs_pg)[0]

		self.sql_commit()

		return record_id


	@staticmethod
	def quote_list(list_type):
		items = []
		for val in list_type: 
			if isinstance(val ,str):
				items.append('"'+val+'"')
			else:
				items.append(str(val))

		quoted_str = "{" + ",".join(items) + "}"
		quoted_str	= quoted_str.replace("'", "''")

		return quoted_str
	

	def sql_expand_array_where(self, spec, key_prefix = '', col_prefix = ''):
		""" Expand a dict so it fits in a WHERE clause
			Logical operator is AND.
		"""
		_spec = spec.copy()

		for k, v in spec.items():
			if isinstance(v, list):
				_spec[k] = self.quote_list(v)

		sql = ' AND '.join(col_prefix + key + 
			( ' IS ' if _spec[key] is None else ' = ' ) +
			'%(' + key_prefix + key + ')s' for key in _spec)
		params = {}
		for key in _spec:
			params[key_prefix + key] = _spec[key]

		return sql, params


	def exist_node(self, node):
		#
		# Verfy if node is already in database.It should comapare all attributes in one row except 'id'. 
		# Notice this verfition is base on the values inserted into db table  is sorted by list.sort().
		# If db data is not sorted, the verfy may be fail beacause we do not check all detail 
		# info stored in db.
		#
		# Parameter node is a dict like {'zone':['zone1', 'zone2'], 'datacenter':['dc1', 'dc2']} 
		#
		for k, v in node.items():
			if v == []:
				node[k] = None

		where, params = self.sql_expand_array_where(node)

		sql = """SELECT count(id) FROM ip_net_node WHERE """ +  where

		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)

		if self._curs_pg.fetchone()[0] > 0:
			return True
		else:
			return False 

	
	def add_node(self, attr):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))

		insert, params = self.sql_expand_insert(attr)

		sql = """INSERT INTO ip_net_node %s RETURNING id""" % insert
		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)
		record_id = next(self._curs_pg)[0]

		self.sql_commit()

		return record_id	


	def add_note(self, attr):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))

		required_attr = ["note"]
		self.verify_attribute(attr, required_attr)

		insert, params = self.sql_expand_insert(attr)
		sql = "INSERT INTO ip_net_note %s RETURNING id" % insert
		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)

		record_id = next(self._curs_pg)[0]

		self.sql_commit()

		return record_id

	def exist_user(self, user_mail):
		sql = "SELECT count(id) FROM ip_net_user WHERE mail = '%s'" % user_mail

		self._logger.info("Execute: SQL:%s." % sql)
		self.sql_execute(sql)

		if self._curs_pg.fetchone()[0] > 0:
			return True
		else:
			return False 

	def add_user(self, attr):
		if not isinstance(attr, dict):
			raise IPAMInvalidValueTypeError("Parameter attr expects dict but gets %s." % type(attr))

		required_attr = [
			"username",
			"mail",
			"erp",
			"phone",
			"department",
			"gm"]

		self.verify_attribute(attr, required_attr)

		insert, params = self.sql_expand_insert(attr)
		sql = "INSERT INTO ip_net_user %s RETURNING id" % insert
		self._logger.info("Execute: SQL:%s. PARAMS:%s" % (sql, params))
		self.sql_execute(sql, params)

		record_id = next(self._curs_pg)[0]

		self.sql_commit()

		return record_id

if __name__ == "__main__":
	ipam = IPAM()
	ipam.connect_db(host="11.3.245.227", port=54321, database="postgres", user="postgres", password="123456")

	prefix_data = {"prefix":"101.236.226.0/24",
			"addrspace":1,
			"reservednode" : 10,
			"provider": 20,
			"casttype": 1,
			"nettype": 1,
			}

	provider_data = {
		"fullname" : "中国北京移动",
		"name":"北京移动",
		"description":"一级运营商；客户经理：某某某"
	}

	node_data = {
		"zone" : [1],
		"datacenter": ["BJS01", "BJS02"],
		"pod":["POD01", "POD02"],
		"rack":["A1-M3-302-H09"],
		"device":["192.168.1.1"]
	}

	note_data = {
		"note": "本记录产生于2017年！"
	}

	user_data = {\
		"username" : "黑子",
		"mail": "heizi@jd.com",
		"erp" : "heizi",
		"phone" : "17212341234",
		"department" : "公有云平台-基础研发-运维部-网络部",
		"gm":"大傻逼"
		}

	assign_data = {
		"prefix":"101.236.226.128/25",
		"vrf":None,
		"reservednode" : None,
		"assignednode": 10,
		"customer": "duanchengping@jd.com",
		"usagetype" : NETWORKDVICEINBANDMANAGEMENTADDRESS,
		"assignstatus" : RESERVED,
		"application" : 1,
		"casttype" : MULTICAST
	}
	try:
		if ipam.get_prefix({"prefix" :assign_data["prefix"], "vrf":"global"}):
			raise Exception("Duplicate Data!")
		a = ipam.assign_prefix(assign_data, refer_prefix="101.236.226.0/24")
		print(a)
	except Exception as e:
		print(e)

	finally:	
		ipam.close_db()


