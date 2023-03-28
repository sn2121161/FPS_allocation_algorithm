# Charge Scheduler

Models the energy demand over time which would result from charging electric vehicles performing a set of routes. In general, this generates a table of half-hour intervals over a period of time, and the energy demand (in kW) of charging each vehicle.

Each run includes multiple route allocations which will run in sequence. So for example a single run (with a run_id = 123) can be set up for multiple route allocations. All of these will run independently. The allocations can be for different stores, different vehicle/charger selections, or even energy efficiencies.

This scheduler supports two charging modes:
* Smart charging: reduces the total electricity costs by charging when the electricity price is cheaper, and also avoids breaching site capacity where possible
* Business as usual: simply chargers at full power when the vehicle arrives regardless of electricity price and total site demand.

The Optimisation is fundamentally a Mixed Integer Programming problem. More information can be found in the [CVXPY documentation](https://www.cvxpy.org/)

[Confluence Page - Pipeline](https://flexpower.atlassian.net/l/cp/dyAEo8aW)

## Inputs and setup

For a new run you will need to set up the following inputs.

* Run parameters (t_run_charging).
Create a new row with:
  * run_id - next available value
  * client_id - based on t_client
  * scheduling_app / scheduling_version - not currently in use but can be used to note git tag of the code or any variations you did
  * charging_mode - can be `["BAU"]` or `["opt"]` or `["opt", "BAU"]`. `opt` means smart charging and `BAU` means business-as-usual (dumb charging).
  * day_start_hours - time of day to start the charge schedules. For regular daily operations it's usually 6 or 7 (representing 6am or 7am). For HGVs usually it's best to leave as 0 (midnight).
  * asc_margin - refers to the extra capacity to use when it's necessary to breach site capacity. Default is 0.2 which means it will use up to 120% of ASC.
  * soc_margin - currently unusued (I think).
  * num_days - number of days to run the optimisation. Usually I run it first with 3 days to make sure that nothing is breaking. Then I make it a high number to just run all the days with routes.
  * allocation_ids - list of allocation IDs to model. Each needs to be in t_allocation and have the corresponding routes in t_route_allocated.

* run ID -
The value of current_run_id in t_system_parameters must match the run ID created in t_run_charging.

* Allocated routes -
These are a collection of routes identified by an allocation ID. The vehicle-route allocations are stored in t_route_allocated, the rest of the route information is in t_route_master and the summary information is in t_allocation.

The following inputs are usually already set up and only need changing when adding new sites or new vehicles.
* Site data -
It's found in t_sites identified by site_id. The site_id comes from the allocation data in t_allocation. The required columns are
  * asc_kw (available site capacity in kW) - if unknown, or if you don't want to restrict the site capacity, just use a very large value
  * distribution_id - refers to the grid distribution. Talk to Jin
  * min_to_connect - how long after a vehicle arrives on site can they be assumed to be plugged in (depends on the site/project, discuss with Michael).

* Site demand -
The total site demand is in t_site_load and it's identified by the site_id. The column used in the optimisation is "clean_load". Note that if this is empty it will be assumed to be 0 (no other site load)

* Electricity price -
The electricity price is in t_electricity_price and is identified by the distribution ID. The columns required are datetime and electricity_price_fixed. Note that if there's no data available it will be filled with a flat default tariff.

* Vehicle specifications -
Stored in t_vehicle_specifications. The useful data is:
  * spec_id - identifies the type of vehicle, matches what's in t_route_allocated under allocated_spec_id
  * battery_size - usable battery capacity in kWh
  * charge_power_ac/dc - charge power for that vehicle in AC or DC mode

## Create local environment

    python -3 -m venv .venv
    .venv\scripts\activate

## Install dependencies

    pip install -r requirements.txt
    git submodule add https://github.com/Flexible-Power-Systems/python_utils.git
    git submodule add https://github.com/Flexible-Power-Systems/pipeline_plan_functions.git
    python setup.py install

Any packages used in the code should go in requirements.txt

## Environment Variables

* Database connection strings (see pipeline_plan_functions.utils.pipe_db_handler.py)
* log_level = DEBUG/INFO/CRITICAL/ERROR/WARNING


## Run app

* run schedule.py - this will run the current_run_id in t_system parameters
* run specific scenarios - If you already created the scenarios in t_charging_scenarios and want to run them again (because they failed, or because you changed something) you can replace the variable `scenarios` in line 5 of schedule.py by a list of scenario IDs. You should first delete any data in t_charge_demand corresponding to those scenario IDs. Then you can run schedule.py

## Structure

Files in scheduling_functions folder.
* controller.py - Reads the inputs from t_run_charging and creates all the scenarios in t_charging_scenarios. Also fetches the necessary allocation data such as vehicle types and chargers.
* schedule_scenario.py - this runs for each scenario ID. It fetches and formats all the required input data, then iterates over each day. For each day it calls the optimiser to solve the scheduling problem and then the cleanup function to export the results. Note: There is a process handler in the part that iterates over each day. If the optimisation takes too long it will kill the process and start the next day.
* optimisation.py - holds all the optimisation functions: problem definition, constraints and solver. The main function is linear_optimiser_V10.
* cleanup.py - exports the new charge schedules and summary information to the database.

## Optimisation Parameters

[This PDF](https://flexpowerltd.sharepoint.com/sites/WEVCMFC/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FWEVCMFC%2FShared%20Documents%2FWP3%20%2D%20Infrastructure%20Hardware%20Development%2FBack%20office%2FAllocation%20and%20Charging%2FFPS%5Fscheduler%5Fv2%2Epdf&parent=%2Fsites%2FWEVCMFC%2FShared%20Documents%2FWP3%20%2D%20Infrastructure%20Hardware%20Development%2FBack%20office%2FAllocation%20and%20Charging) might be useful, but it doesn't strictly match the optimisation in this module (it was written for the back-office charge scheduling)

There are three optimisation modes:
1. normal mode (linear_optimiser_V10) - This the first mode tried. If the optimisation is unfeasible (unable to fill all the constraints) it moves on to breach mode
2. Breach mode (linear_optimiser_breach) - This is used when charging required breaching site capacity by a small amount. If the optimisation is still unfeasible it moves to the magic mode
3. Magic mode (magic_charging) - Is a catch all case for when no solution can be found. This simply assumes a constant charge rate during the full available period, regardless of charger power, price or site capacity.

### Optimisation Variables
* `outputs` is the main variable. It refers to the energy required in each time period (T) for each vehicle (N) in kWh.

        outputs = cp.Variable((T, N), nonneg=True)

* `chargerM2` is the choice of charger for each session. 1 for fast charger (DC) and 0 for slow charger (AC).

        chargerM2 = cp.Variable((T, N), boolean=True)

### Optimisation Objective

Minimisation objective

    objective = cp.Minimize(
        cp.sum(prices @ outputs)  # reduce total electricity costs
        - 100000*cp.sum(outputs)  # maximises amount of energy delivered
        + cp.sum(timepricing @ outputs)  # encourages charging earlier
        )

### Optimisation Constraints

* Restrict the batteries from going under 0% or over 100%
* Limit the number of fast chargers based on the input parameters
* Limit the charge rate of each vehicle based on the vehicle max AC/DC rate and the available chargers
* Use the same charger for each charging sessions. This ensures the schedule doesn't require moving a vehicle from an AC charger to a DC charger. The time periods for a single charging session are "bound together" so they use the same charger.
* Limit overall charge capacity. In the "breach" scenario this allows for a small amount of site capacity breach.


