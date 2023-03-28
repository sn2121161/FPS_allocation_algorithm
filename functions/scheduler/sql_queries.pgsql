-- DELETE FROM t_charging_scenarios;
-- ALTER TABLE t_charging_scenarios
-- ADD charger_type varchar;
-- DELETE FROM t_charging_scenarios WHERE run_id=22;
SELECT * FROM "t_charging_scenarios" LIMIT 10;

-- UPDATE t_run_charging SET allocation_ids='[64, 65]' WHERE run_id=22;
SELECT * FROM t_run_charging;

-- UPDATE t_system_parameters SET parameter_value=22 WHERE parameter_name='current_run_id';
-- SELECT * FROM t_system_parameters;

-- SELECT * FROM t_allocation WHERE run_id=21
-- SELECT * FROM t_allocation WHERE allocation_id IN (64, 65)

-- DELETE FROM t_charge_demand;
SELECT * FROM t_charge_demand



