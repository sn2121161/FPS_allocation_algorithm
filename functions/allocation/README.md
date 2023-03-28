# Vehicle-Route allocation

This is Python library designed to allocate a selection of transport routes to a set of vehicles. These tools can also be used to analyse the feasibility of completing the set of routes with an electric vehicle fleet.

The main input of this file is a collection of routes which are stored in the pipeline database (PipelineDB-New)

## Installation

### Create local environment

    python -3 -m venv .venv
    .venv\scripts\activate

### Install dependencies

    pip install -r requirements.txt
    git submodule add https://github.com/Flexible-Power-Systems/python_utils.git
    git submodule add https://github.com/Flexible-Power-Systems/pipeline_plan_functions.git
    python setup.py install

The requirements for the feasibility analysis aren't in requirements.txt yet.

## Submodules

All of the pipeline modules depend on two external sub-modules:

* pipeline_plan_functions - database handling, cloud storage (blob storage), generic functions for new clients.
* python_utils - mostly used for the logger function. Contact Kiyoto

## Main Allocation Functionality

The main functionality of this library is to assign vehicles to routes using a linear optimisation method. This app is designed to do multiple "allocations" in a sequence, where each allocation refers to a single set of routes (defined by site, date and route source) and a single set of inputs (e.g vehicle choice, vehicle energy efficiency). Of course, the individual functions can be imported individually for specific requirements.

The relevant modules are:

* controller.py: This module takes the run inputs and creates a master allocation table
* alloction_scenario.py: this gathers all the route, vehicle, charger and site data. It also calculates the starting number of vehicles and individual route feasbility.
* daily.py: iterates over each day and calculates the optimal vehicle-route selection for each day. This process is done in shifts, so each shift gets assigned in turn, based on what the vehicles have already done that day. The key to this process is the cost matrix:
  * The Cost matrix (`cost_matrix()`) has a row for each route in the shift and a column for each vehicle. Each cell corresponds to a specific vehicle-route combination and the value in that cell is the score. A score between 0 and 1 indicates that that vehicle is able to complete that route, with a lower score if it requires extra charging between shifts. A negative score indicates that the route is unfeasible, which can be due to time, payload (weight), number of crates (volume) or energy requirements. This cost matrix may need to be modified as the projects evolve.
* cleanup.py - combines the allocation results, updates the final allocations to the database and calculates some summary information that is updated to the t_allocation database.
* mixed.py - not currently in use. This module was meant to look at mixed fleet feasibility without changing the route combinations, but there are some issues and needs to be rebuilt.

### Set up the run(s) inputs

Enter a new row in t_run_allocation
* client_id use the lookup table in t_clients
* allocation_app -  use allocate.py for regular operations.
* sites - list of site IDs you want to run. Use the list in t_sites
* start_date / end_date - defines the period you want to look at. The end_date is a strict inequality, so if the end date is "2021-11-06 00:00:00"  it will look at routes up to the 5th November, not the 6th
* vehicles - this can take multiple formats. The vehicle specification IDs can be taken from the t_vehicle_specification table. For simplicity use this format: `[[<ev_spec_id>], [<diesel_spec_id>]]`. You can leave either the `ev_spec_id` or `diesel_spec_id` empty.
* xmpg_change is a variation on the basic energy efficiency. Leave 0 unless you want to do a sensitivity analysis
* chargers - format `[<ac_charger>, <dc_carger>]`. If you only want to use one type of charger use the same value.
* route_table - use t_route_master
* cap_vehicles - Would you like to limit the number of vehicles? If True, the unfeasible routes just get discarded, if False the number of vehicles can increase to accommodate more routes. By default leave False.
* Mixed fleet - leave as `[]`
* Source - Use the source ID of your routes in t_route_master
* num_v - Leave empty or give a minimum number of vehicles to use in the allocation

### Run the allocation app
Update the allocate.py file, variable RUNS with the run IDs you created in the previous step..
```python
import allocate
allocate.main()
```

## Feasibility Analysis

Feasibility analysis in this case is modelling the requirements of a certain logistics operation, based on the vehicle routes, depots, patterns, etc and determining if they would be feasible using a certain combination of electric vehicles and chargers.

Many of the consulting projects use a set of common functions which can be found in feasibility_functions.py. However, each project requires extensive adjustment, so most of the work is done in Jupyter Notebooks and the functions evolve quickly.

The are also some functions in that module for plots and graphs used in reports. Again, these are more of a starting point and they get adjusted for each project.

The feasibility analysis may or may not be done in conjuction with the allocation process. For example, some of the Van projects require an initial feasibility analysis to first get a rough estimate of the requirements, then the routes are allocated and a final feasibility analysis happens at the end.

For the HGV projects we haven't actually done any vehicle allocations, but instead relied on the actual vehicle duties. Therefore this process doesn't bear any resemblance to the main allocation process, but it does use some of the same database tables.

hgv_template.ipynb is given as a guide to an HGV feasibility analysis. Please note that this process hasn't been formalised or reviewed properly.

hgv4_imperial.ipynb is an example of outputs generated for a feasibility analysis.
