--
-- Calculate the uniform id from timestamp.
--
CREATE OR REPLACE FUNCTION md5_timestamp() RETURNS text AS $_$  
DECLARE
	time_t text;
BEGIN
	time_t := to_char(now(), 'YYYY-HH:MM:SS:MS:US')||random();
	RETURN md5(time_t);
END;
$_$ LANGUAGE plpgsql;


--
-- Define trigger on INSERT, UPDATE, DELETE rows of ip_net_assign table.
--

CREATE OR REPLACE FUNCTION tg_log_assign_operation() RETURNS trigger AS $tg_log$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO ip_net_assign_log SELECT NEW.recordid, 'insert', now(), user, NEW.*;
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO ip_net_assign_log SELECT NEW.recordid, 'update', now(), user, OLD.*;
        RETURN OLD;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO ip_net_assign_log SELECT md5(to_char(now(), 'YYYY-HH:MM:SS:MS:US')||random()), 'delete', now(), user, OLD.*;
        RETURN OLD;
    END IF;
END;
$tg_log$ LANGUAGE plpgsql;

--
-- Applay trigger on table ip_net_assign.
--
CREATE TRIGGER trigger_log_assign_operation 
AFTER INSERT OR UPDATE OR DELETE ON ip_net_assign
    FOR EACH ROW EXECUTE PROCEDURE tg_log_assign_operation();



--
-- INSERT, UPDATE table ip_net_node.
--
CREATE OR REPLACE FUNCTION update_ip_net_node(region int4[], datacenter varchar(10)[], pod varchar(10)[], rack varchar(15)[], device varchar(39)[], opt text, node_idx int4) RETURNS numeric AS $_$  
DECLARE
    record_idx numeric;
    record_num numeric;
    error_code numeric;
BEGIN

    IF update_ip_net_node.opt = 'delete' THEN
        SELECT count(*) INTO record_num
        FROM ip_net_assign WHERE reservednode = update_ip_net_node.node_idx
        OR assignednode = update_ip_net_node.node_idx; 
        IF record_num = 0 THEN
            DELETE FROM ip_net_node WHERE ip_net_node.idx = update_ip_net_node.node_idx;
            RETURN node_idx;
        END IF;

        --Could not delete the record for it is used.
        error_code = -2; 
        RETURN error_code;
    END IF;

    SELECT ip_net_node.idx INTO record_idx 
    FROM ip_net_node WHERE ip_net_node.region = update_ip_net_node.region
    and ip_net_node.datacenter = update_ip_net_node.datacenter
    and ip_net_node.pod = update_ip_net_node.pod
    and ip_net_node.rack = update_ip_net_node.rack
    and ip_net_node.device = update_ip_net_node.device;

    IF NOT FOUND THEN
        INSERT INTO ip_net_node(region, datacenter, pod, rack, device) VALUES(
            update_ip_net_node.region,
            update_ip_net_node.datacenter,
            update_ip_net_node.pod,
            update_ip_net_node.rack,
            update_ip_net_node.device
        ) RETURNING idx INTO record_idx ;
        IF NOT FOUND THEN
            --Failed to insert value.
            error_code = -1;
            RETURN error_code;
		END IF;

        IF update_ip_net_node.opt = 'update' THEN
            UPDATE ip_net_assign SET reservednode = record_idx
            WHERE reservednode = update_ip_net_node.node_idx;

            UPDATE ip_net_assign SET assignednode = record_idx
            WHERE assignednode = update_ip_net_node.node_idx;
        END IF;
	END IF;
    RETURN record_idx;
END;
$_$ LANGUAGE plpgsql;