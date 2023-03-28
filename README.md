# Van Pipeline Running Procedures

This is a pipeline designed for van operations with one specific depot. There are three major components of the pipeline:

* Vehicl-Route Allocation: it allocates a selection of transport routes to a set of vehicles. 
* Charge Scheduler: it generates a table of half-hour intervals over a given period of time, and the energy demand of charging for each vehicle.
* TCO Calculation: it calculates the total cost of ownership for both chargers and vehicles.

All the data are stored in the pipeline database (Pipeline-DB-New). If you wish to perform a test first, please use data in Pipeline-DB-Dev. Contact Atakan for the access. 

## Essential Data before Running the Pipeline

You may want to check if the following data are already stored in the pipeline database. 

* Route data: stored in `t_route_master`
* Vehicle data: stored in `t_vehicle_specification`
* Charger data: stored in `t_charger_specification`
* Client data: stored in `t_client`
* Site data: stored in `t_sites` and `t_ site_load_meter_breakdown` (which may not contain any data for now. If that's the case, just ignore this table)
* Financial data: stored in `t_elecricity_price`, `t_capital_allowances`, `t_residual_values`
* Global parameters: stored in `t_system_parameters`

For details about these tables (e.g. meaning of the column names), please refer to https://flexpowerltd.sharepoint.com/:x:/r/sites/PlanPipeline/_layouts/15/Doc.aspx?sourcedoc=%7B43D9BCB6-54E6-4744-BD83-3C569FC71121%7D&file=22-02.Plan_System_Arch.ST.01.xlsx&action=default&mobileredirect=true&DefaultItemOpen=1 (Database Tables). Contact Ben for the access.

## Main Procedures

There are five procedures to run the pipeline:

* Run the allocation function
    * Create the local environment and set up environment variables to run the script. For more details please refer to https://github.com/Flexible-Power-Systems/fps_pipeline_plan/tree/st-allocation/functions/shared_functions/allocation.  
    * Manually enter a new row in `t_run_allocation`. For details please refer to the same link above.
    * Run the `allocate.py` file.
    * The outputs would be stored and updated in `t_allocation` and `t_route_allocated`.

* Run the vehicle tco calculation function 
    * Manually enter a new row in `t_run_vehicle_tco`. Please note: The `<run_id>` here should be the same as the `<run_id>` in `t_allocation`.
    * Manually input `<run_id>`, `<client_id>`, and `<site_id>` in `tco_vehicle.py` file, and they should be the same as values in `t_allocation`.
    * Run the `tco_vehicle.py` file.
    * The outputs should be stored and updated in `t_allocation`, columns `<premilinary_tco_lease>` and `<premilinary_tco_purchase>`.

* Filter Allocations
    * Manually update `<schedule_charger>` = 2 in `t_allocation` for allocations that meet the client’s demand.
    * The purpose of this step is to reduce the computational time in charging scheduler.

* Run the charging schedule function 
    * Create the local environment and set up environment variables to run the script. For more details please refer to https://github.com/Flexible-Power-Systems/fps_pipeline_plan/tree/st-allocation/functions/shared_functions/scheduler.
    * Manually enter a new row in `t_run_charging`. For details please refer to the same link above.
    * Manually update the `<current_run_id>` in `t_system_parameters` to the `<run_id>` entered in the previous step. 
    * Run the `schedule.py` file.
    * The outputs would be stored and updated in `t_charging_scenarios` and `t_charging_demand`.

* Run the vehicle and charger tco calculation functions
    * Manually enter a new row in `t_run_charger_tco`. The `<run_id>` should be same as the `<run_id>` in `t_allocation`.
    * Manually input `<run_id>`, `<client_id>` in `tco_charger.py` file and `<run_id>`, `<client_id>` and `<site_id>` in `tco_vehicle.py` file.
    * Run the `tco_charger.py` and `tco_vehicle.py` files.
    * The outputs would be stored and updated in `t_charger_tco_components` and `t_vehicle_tco_components`.

## Further Development

This section is added to record developments made in the pipeline (continuously updating)

* New features/columns
    * Added `<soc_min>` and `<soc_max>` columns in `t_charging_scenarios`. We want to make sure that `<soc_min>` should above 0 and `<soc_max>` should below 100.
    * Added `<vehicle_soc>` in `t_charge_demand`. We can monitor `<vehicle_soc>` for every time intervel now.

Following changes are not directly relevant to the running procedures, please ignore them when trying to run the pipeline.

* QA Checks
    * Check that for each scenario, for each half hour charging period, no more than the allowed number of rapids are being used. 
    * Check that for each half hour charging period, the output power is bigger or equal to vehicle_soc change from the previous half hour period.

