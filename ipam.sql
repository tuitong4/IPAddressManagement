
CREATE TABLE ip_net_assign (
    "recordid" varchar(32) DEFAULT NULL,
    "prefix" inet DEFAULT NULL,
    "addrspace" int4 DEFAULT NULL,
    "vrf" varchar(10) DEFAULT 'global',
    "reservednode" int4 DEFAULT NULL,
    "assignednode" int4 DEFAULT NULL,
    "expires" date DEFAULT NULL,
    "industry" int4 DEFAULT NULL,
    "provider" varchar(20) DEFAULT NULL,
    "customer" varchar(20) DEFAULT NULL,
    "assignstatus" int4 DEFAULT 0,
    "description" int4 DEFAULT NULL,
    "comments" int4 DEFAULT NULL,
    "tags" int4 DEFAULT NULL,
    "application" int4 DEFAULT NULL,
    "addrfamily" int4 NOT NULL,
    "casttype" int4 DEFAULT NULL,
    "nettype" int4 DEFAULT NULL,
    "shared" bool DEFAULT true,
    "usagetype" int4 DEFAULT NULL,
    "leaf" bool DEFAULT false,
    "root" bool DEFAULT false,
    "updatetime" timestamp null,
    "originalid" varchar(32) DEFAULT NULL,
    PRIMARY KEY ("prefix", "vrf")
);

COMMENT ON COLUMN "ip_net_assign"."addrspace" IS 'internet(1), intranet(2)';
COMMENT ON COLUMN "ip_net_assign"."industry" IS 'JDCOM(1),JDCLOUD(2)';
COMMENT ON COLUMN "ip_net_assign"."assignstatus" IS 'Idle(0), Reserved(1), Assigned(2), Quarantine(3)';
COMMENT ON COLUMN "ip_net_assign"."addrfamily" IS 'IPv4(4), IPv6(6)';
COMMENT ON COLUMN "ip_net_assign"."casttype" IS 'Unicast(1), Anycast(2), Multicast(3)';
COMMENT ON COLUMN "ip_net_assign"."nettype" IS 'Dynamic(BGP)(1), ProxyCast(2), ChinaTelecom(3), ChinaUnicom(4), ChinaMobile(5), Common(6), DualDynamic(BGP)(7), EducationNetwork(8), null(0)';
COMMENT ON COLUMN "ip_net_assign"."usagetype" IS 'ServerServiceAddress(1), ServerManagentAddress(2), VitrualServerAddress(3), NetworkDviceInbandManagementAddress(4), NetworkDviceInbandManagementAddress(5), NetworkDeviceInterconnectionAddress(6), ServerInterconnectionAddress(7)';
COMMENT ON COLUMN "ip_net_assign"."root" IS 'True means root node.';


CREATE TABLE ip_net_assign_log (
    "idx" varchar(32) DEFAULT NULL,
    "operation" varchar(6) DEFAULT NULL,
    "optime" timestamp DEFAULT NULL,
    "user" text DEFAULT NULL,
    "recordid" varchar(32) DEFAULT NULL,
    "prefix" inet DEFAULT NULL,
    "addrspace" int4 DEFAULT NULL,
    "vrf" varchar(10) DEFAULT NULL,
    "reservednode" int4 DEFAULT NULL,
    "assignednode" int4 DEFAULT NULL,
    "expires" date DEFAULT NULL,
    "industry" int4 DEFAULT NULL,
    "provider" varchar(20) DEFAULT NULL,
    "customer" varchar(20) DEFAULT NULL,
    "assignstatus" int4 DEFAULT 0,
    "description" int4 DEFAULT NULL,
    "comments" int4 DEFAULT NULL,
    "tags" int4 DEFAULT NULL,
    "application" int4 DEFAULT NULL,
    "addrfamily" int4 NOT NULL,
    "casttype" int4 DEFAULT NULL,
    "nettype" int4 DEFAULT NULL,
    "shared" bool DEFAULT true,
    "usagetype" int4 DEFAULT NULL,
    "leaf" bool DEFAULT NULL,
    "root" bool DEFAULT NULL,
    "updatetime" timestamp null,
    "originalid" varchar(32) DEFAULT NULL,
    PRIMARY KEY ("idx")
);


CREATE TABLE ip_net_provider (
    "idx" serial4,
    "fullname" text DEFAULT NULL,
    "shortname" text,
    "description" text DEFAULT NULL,
    PRIMARY KEY ("shortname")
);


CREATE TABLE ip_net_node(
	"idx" serial4 PRIMARY KEY,
	"region" int4[] DEFAULT NULL,
	"datacenter" varchar(10)[] DEFAULT NULL,
	"pod" varchar(10)[] DEFAULT NULL,
	"rack" varchar(15)[] DEFAULT NULL,
	"device" varchar(39)[] DEFAULT NULL
);

COMMENT ON COLUMN "ip_net_node"."region" IS 'Northern(1), Eastern(2), Southern(3), Western(4), Central(5), VERSEAN(6)';
COMMENT ON COLUMN "ip_net_node"."device" IS 'Device is a switch or a server''s management ip address';


CREATE TABLE ip_net_note(
	"idx" serial4 PRIMARY KEY,
    "note" text 
);


CREATE TABLE ip_net_user(
    "idx" serial4,
    "username" varchar(10),
    "mail" varchar(20) PRIMARY KEY,
    "erp" varchar(15) DEFAULT NULL,
    "phone" varchar(11) DEFAULT NULL,
    "department" varchar(50) DEFAULT NULL,
    "gm"  varchar(20) DEFAULT NULL
);