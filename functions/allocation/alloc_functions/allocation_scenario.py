import numpy as np
import pandas as pd
import os
import psycopg2
# import sqlalchem
import datetime as dt
import json
import pipeline_plan_functions.utils.pipe_db_handler as dbh
import pipeline_plan_functions.utils.data_types as dth
# import pipeline_plan_functions.utils.data_handler as rh
from python_utils.utils.logger import logger
logger.setLevel(os.getenv('log_level', "DEBUG"))
DERROGATION = 725


def find_current_allocation(run, cnx):
    current_alloc = None
    not_last = False  # This would imply that there are no more allocations
    try:
        sql_query = f"""SELECT * FROM t_allocation WHERE run_id={run} AND allocated!='c'
                ORDER BY allocation_id ASC """
        allocations = pd.read_sql_query(sql_query, cnx)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching allocation table")
        raise error
    not_in_progress = ~(allocations['allocated'] == 'p').any()
    number_pending = len(allocations[allocations['allocated'] == 'n'])
    if not_in_progress:
        if number_pending > 0:
            current_alloc = allocations.iloc[0].to_dict()
            current_alloc['vehicle_pool'] = json.loads(
                current_alloc['vehicle_pool'])
            not_last = number_pending > 1
            logger.debug(
                f"Current allocation ID: {current_alloc['allocation_id']}")
        else:
            logger.info(
                "No pending allocations to run")
    else:
        logger.info("Allocation already in process")
    return current_alloc, not_last


def get_allocation(idx, cnx):
    try:
        sql_query = f"""SELECT * FROM t_allocation WHERE allocation_id={idx}
                ORDER BY allocation_id ASC """
        allocations = pd.read_sql_query(sql_query, cnx)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching allocation table")
        raise error
    current_allocation = allocations.iloc[0].to_dict()
    current_allocation['vehicle_pool'] = json.loads(
        current_allocation['vehicle_pool'])
    logger.debug(
        f"Current allocation ID: {current_allocation['allocation_id']}")
    return current_allocation


def get_return_routes(table, site, start, end, cnx, source=None):
    try:
        if source is None:
            sql_query = f"""SELECT *  FROM {table} WHERE departure_time >= '{start}'
                AND departure_time < '{end}'
                AND site_id_start={site}"""
        else:
            sql_query = f"""SELECT *  FROM {table} WHERE departure_time >= '{start}'
                AND departure_time < '{end}'
                AND site_id_start={site}
                AND source={source}"""
        routes = pd.read_sql_query(sql_query, cnx)
        routes['payload'] = routes['payload'].astype(float).fillna(0)
        routes['number_crates'] = routes['number_crates'
                                         ].astype(float).fillna(0)
        routes['date'] = pd.to_datetime(routes['departure_time'].dt.date)
        assert len(routes) > 0
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching routes/no routes available")
        raise error
    # If there are any routes that end in another site, add a day
    # to the return time so they're not available after they leave
    not_return = routes['site_id_end'] != routes['site_id_start']
    routes.loc[not_return, 'arrival_time'] += dt.timedelta(days=1)
    return routes


def get_site_data(site, cnx):
    try:
        sql_query = f"SELECT * FROM t_sites WHERE site_id={site}"
        site_data = pd.read_sql_query(sql_query, con=cnx).loc[0].to_dict()
        site_data['shift_starts'] = json.loads(site_data['shift_starts'])
    except (Exception, psycopg2.Error) as error:
        logger.error("Error getting site data")
        raise error
    return site_data


def set_shifts(shift_starts_hours, routes):
    shifts = pd.Series(index=routes.index, dtype=int)
    start_times = dth.get_hours(routes['departure_time'])
    for i, start_hour in enumerate(shift_starts_hours):
        shifts.loc[start_times >= start_hour] = i+1
    return shifts


def get_vehicle_specs(vehicles, cnx):
    if len(vehicles) > 0:
        if len(vehicles) == 1:
            vehicle_string = f"({vehicles[0]})"
        else:
            vehicle_string = tuple(vehicles)
        try:
            sql_query = (
                f"""SELECT spec_id, energy_use, battery_size, charge_power_ac, charge_power_dc,
                max_load, max_crate, fuel_type FROM t_vehicle_specification
                WHERE spec_id IN {vehicle_string}""")
            specs = pd.read_sql_query(sql_query, cnx, index_col='spec_id')
        except (Exception, psycopg2.Error) as error:
            logger.error("Error reading vehicle specs")
            raise error
    else:
        specs = None
    return specs


def feasible_journey(veh, routes, xmpg):
    reqE = (routes['distance_miles'] * veh['energy_use'])/xmpg
    feasE = reqE < veh['battery_size']
    feasP = routes['payload'] < veh['max_load'] + DERROGATION
    feasVOL = routes['number_crates'] < veh['max_crate']
    feas = feasE & feasP & feasVOL
    return feas


def select_vehicle(routes, vspecs, xmpg, icevehicle, threshold=0.05):
    potential_vehicles = []
    potential_unallocated = []
    selected_vehicle = ''
    if vspecs is None:
        vehicle2 = icevehicle[0]
        vehicle1 = icevehicle[0]
        return vehicle1, vehicle2
    elif len(vspecs) == 1:
        threshold = 1
    elif len(icevehicle) == 1:
        threshold = 0.5
    for vidx in vspecs.index:
        feas = feasible_journey(vspecs.loc[vidx], routes, xmpg)
        njourneys = len(feas)
        nunfeas = njourneys - feas.sum()
        if nunfeas/njourneys < threshold:
            logger.debug(f"Potential Vehicle: {vidx}")
            potential_vehicles.append(vidx)
            potential_unallocated.append(nunfeas)
    if len(potential_vehicles) > 0:
        idx = potential_unallocated.index(min(potential_unallocated))
        selected_vehicle = potential_vehicles[idx]
        logger.debug(f'Best: {selected_vehicle} '
                     f'with {potential_unallocated[idx]} routes removed')
    if len(icevehicle) == 0:
        vehicle2 = selected_vehicle
        vehicle1 = selected_vehicle
    else:
        vehicle2 = icevehicle[0]
        vehicle1 = selected_vehicle
    return vehicle1, vehicle2


def num_simultaneous(routes):
    # Calculate max number of simultaneous journeys
    dates = routes['date'].unique()
    N = 0
    minutes = 2
    for date in dates:
        ntimeperiods = int(60*24/minutes)   # (5 minutes)
        tps = np.array([date + i*np.timedelta64(minutes, 'm')
                        for i in range(ntimeperiods)])
        count_busy = np.zeros(ntimeperiods)
        for route in routes[routes['date'] == date].index:
            unavailable = ((tps > routes.loc[route, 'departure_time'])
                           & (tps < routes.loc[route, 'fixed_arrival']))
            count_busy += unavailable.astype(int)
        N = max(N, count_busy.max())
    count_routes_shift = routes.groupby(
        ['date', 'shift']
        )['allocation_id'].count().max()
    N = max(N, count_routes_shift)
    logger.debug(f'Number of Vehicles is {N}')
    return N


def update_alloc(alloc, connection, cur):
    column_names = ['vehicle1', 'vehicle2', 'num_v', 'num_r', 'xmpg',
                    'num_v_final']
    column_string = ", ".join([f"{c}={alloc[c]}" for c in column_names])
    try:
        sql_query = f"""UPDATE t_allocation
            SET allocated='p', {column_string}
            WHERE allocation_id={alloc['allocation_id']};"""
        cur.execute(sql_query)
        connection.commit()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updation t_allocation table")
        raise error
    return


def main(idx):
    not_last = False
    try:
        logger.info(f"Allocation function called at {dt.datetime.now()}")
        connection, cur = dbh.database_connection('test')
        cnx = dbh.create_alch_engine()
        # run = rh.get_current_run(connection, cur)
        # Read the allocation table, find the last one
        # alloc, not_last = find_current_allocation(run, cnx)
        alloc = get_allocation(idx, cnx)
        # Get the journeys
        routes = get_return_routes(alloc['route_table'], alloc['site_id'],
                                   alloc['start_date'], alloc['end_date'],
                                   cnx, alloc['source'])
        site_data = get_site_data(alloc['site_id'], cnx)
        # Assign shifts
        routes['shift'] = set_shifts(site_data['shift_starts'], routes)
        routes['fixed_arrival'] = (
            routes['arrival_time']
            + dt.timedelta(minutes=site_data['turnaround_time']))
        routes['allocation_id'] = alloc['allocation_id']
        alloc['xmpg'] = site_data['xmpg']*(1+alloc['xmpg_change']/100)
        vehicle_specs = get_vehicle_specs(alloc['vehicle_pool'][0], cnx)
        # Select vehicles (if only one in pool, just that)
        alloc['vehicle1'], alloc['vehicle2'] = select_vehicle(
            routes, vehicle_specs, alloc['xmpg'], alloc['vehicle_pool'][1])
        if len(alloc['vehicle_pool'][1]) == 0:
            feas = feasible_journey(vehicle_specs.loc[alloc['vehicle2']],
                                    routes, alloc['xmpg'])
            routes = routes[feas]
        alloc['num_r'] = len(routes)
        # Get the number of vehicles
        calculated_num_v = num_simultaneous(routes)
         # Bill editing
        if isinstance(alloc['num_v'], type(None)):
            alloc['num_v'] = calculated_num_v
        else:
            alloc['num_v'] = max(alloc['num_v'], calculated_num_v)
        alloc['num_v_final'] = alloc['num_v']
        # Create rows in t_route_allocated
        upload_cols = ['route_id', 'allocation_id', 'date', 'shift']
        dbh.upload_table(routes[upload_cols], 't_route_allocated')
        update_alloc(alloc, connection, cur)
    except Exception as e:
        logger.error(e)
        SystemExit(e)
    finally:
        cnx.dispose()
        cur.close()
        connection.close()
        logger.info("Closed db connection")
    return not_last


if __name__ == '__main__':
    main()
       
