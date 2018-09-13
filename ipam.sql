CREATE TABLE "public"."ipaddress" (
  "addrspace" int2 DEFAULT NULL,
  "vrf" char(10) COLLATE "pg_catalog"."default" DEFAULT 'global'::bpchar,
  "appretain" int4 DEFAULT NULL,
  "location" int4 DEFAULT NULL,
  "expires" date DEFAULT NULL,
  "industry" int2 DEFAULT NULL,
  "provider" char(20) COLLATE "pg_catalog"."default" DEFAULT NULL::bpchar,
  "customer" char(20) COLLATE "pg_catalog"."default" DEFAULT NULL::bpchar,
  "assignstatus" int2 DEFAULT 0,
  "description" int4 DEFAULT NULL,
  "comment" int4 DEFAULT NULL,
  "tags" int4 DEFAULT NULL,
  "application" int2 DEFAULT NULL,
  "addrfamily" int2 NOT NULL DEFAULT NULL,
  "casttype" int2 DEFAULT NULL,
  "nettype" int2 DEFAULT NULL,
  "share" bool DEFAULT true,
  "usagetype" char(30) COLLATE "pg_catalog"."default" DEFAULT NULL::bpchar,
  "prefix" inet NOT NULL DEFAULT NULL,
  "prefixid" int4 NOT NULL DEFAULT nextval('ipaddress_prefixid_seq'::regclass),
  "parentprefix" int4 NOT NULL DEFAULT NULL,
  CONSTRAINT "ipaddress_pkey" PRIMARY KEY ("prefix"),
  CONSTRAINT "prefixid_unikey" UNIQUE ("prefixid")
)
;

ALTER TABLE "public"."ipaddress" 
  OWNER TO "postgres";

COMMENT ON COLUMN "public"."ipaddress"."addrspace" IS 'internet(1), intranet(2)';

COMMENT ON COLUMN "public"."ipaddress"."industry" IS 'JDCOM(1),JDCLOUD(2)';

COMMENT ON COLUMN "public"."ipaddress"."assignstatus" IS 'Idle(0), Reserved(1), Assigned(2), Quarantine(3)';

COMMENT ON COLUMN "public"."ipaddress"."addrfamily" IS 'IPv4(4), IPv6(6)';

COMMENT ON COLUMN "public"."ipaddress"."casttype" IS 'Unicast(1), Anycast(2), Multicast(3)';

COMMENT ON COLUMN "public"."ipaddress"."nettype" IS 'Dynamic(BGP)(1), ProxyCast(2), ChinaTelecom(3), ChinaUnicom(4), ChinaMobile(5), Common(6), DualDynamic(BGP)(7), EducationNetwork(8), null(0)';

COMMENT ON COLUMN "public"."ipaddress"."usagetype" IS 'ServerServiceAddress(1), ServerManagentAddress(2), VitrualServerAddress(3), NetworkDviceInbandManagementAddress(4), NetworkDviceInbandManagementAddress(5), NetworkDeviceInterconnectionAddress(6), ServerInterconnectionAddress(7)';

COMMENT ON COLUMN "public"."ipaddress"."parentprefix" IS '0 means root node.';



CREATE TABLE ip_net_assign (
    "id" serial2,
    "prefix" inet PRIMARY KEY,
    "addrspace" int2 DEFAULT NULL,
    "vrf" char(10) DEFAULT 'global',
    "reservednode" int2 DEFAULT NULL,
    "assignednode" int2 DEFAULT NULL,
    "expires" date DEFAULT NULL,
    "industry" int2 DEFAULT NULL,
    "provider" char(20) DEFAULT NULL,
    "customer" char(20) DEFAULT NULL,
    "assignstatus" int2 DEFAULT 0,
    "description" int2 DEFAULT NULL,
    "comment" int2 DEFAULT NULL,
    "tags" int2 DEFAULT NULL,
    "application" int2 DEFAULT NULL,
    "addrfamily" int2 NOT NULL,
    "casttype" int2 DEFAULT NULL,
    "nettype" int2 DEFAULT NULL,
    "share" bool DEFAULT true,
    "usagetype" int2 DEFAULT NULL,
    "leaf" bool DEFAULT false,  
)