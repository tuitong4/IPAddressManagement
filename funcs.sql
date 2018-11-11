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
        INSERT INTO ip_net_assign_log SELECT NEW.recordid, "insert", now(), user, NEW.*;
        RETURN NEW;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO ip_net_assign_log SELECT NEW.recordid, "update", now(), user, OLD.*;
        RETURN OLD;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO ip_net_assign_log SELECT NEW.recordid, "delete", now(), user, OLD.*;
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



select row_to_json(r) from (select * from ip_net_assign) r
