# Equivalent to calculate_shift
# Allocate journeys to vehicles in a day
# This is the part that takes most time

import numpy as np
import pandas as pd
import os
import psycopg2
# import sqlalchemy
import datetime as dt
# import json
import pipeline_plan_functions.utils.pipe_db_handler as dbh
# import pipeline_plan_functions.utils.data_types as dth
# import pipeline_plan_functions.utils.data_handler as rh
from python_utils.utils.logger import logger
# from pulp import LpMaximize
import pulp
logger.setLevel(os.getenv('log_level', "DEBUG"))

CHARGER_EFF = 0.9
# TP_FRACT = 0.5
TIME_INT_IS = dt.timedelta(minutes=30)
TP_FRACT_IS = TIME_INT_IS/dt.timedelta(hours=1)
DERROGATION = 725


def find_current_allocation(cnx):
    try:
        sql_query = """SELECT * FROM t_allocation WHERE allocated='p'
                ORDER BY allocation_id ASC LIMIT 1"""
        current_allocation = pd.read_sql_query(
            sql_query, cnx).iloc[0].to_dict()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching current allocation")
        raise(error)
    return current_allocation


def get_allocation(idx, connection, cur):
    try:
        sql_query = f"""SELECT * FROM t_allocation WHERE allocation_id={idx}
                ORDER BY allocation_id ASC """
        cur.execute(sql_query)
        connection.commit()
        allocation_fetch = cur.fetchall()
        desc = cur.description
        current_allocation = {
            desc[i][0]: allocation_fetch[0][i] for i in range(len(desc))
        }
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching allocation table")
        raise error
    return current_allocation


def get_daily_routes(date, allocation_id, connection, cur):
    try:
        sql_query = f"""SELECT *  FROM t_route_allocated
            WHERE date='{date}' AND allocation_id={allocation_id}"""
        cur.execute(sql_query)
        connection.commit()
        routes_fetch = cur.fetchall()
        desc = cur.description
        column_names = [col[0] for col in desc]
        routes = pd.DataFrame(routes_fetch, columns=column_names)
        routes.set_index('route_id', inplace=True)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching routes/no routes available")
        raise error
    return routes


def get_daily_route_data(routes, params, connection, cur):
    # Fetch the original route data required and merges it all together
    orig_routes = get_routes_fromid(routes.index, params['route_table'],
                                    params['source'], connection, cur)
    route_cols = ['departure_time', 'arrival_time', 'distance_miles',
                  'payload', 'number_crates']
    routes = routes.merge(orig_routes[route_cols], left_index=True,
                          right_index=True)
    routes['route_cost'] = 0
    routes['allocated_vehicle_id'] = 0
    routes['equivalent_mileage'] = routes['distance_miles'] / params['xmpg']
    routes['payload'] = routes['payload'].astype(float).fillna(0)
    routes['number_crates'] = routes['number_crates'].fillna(0)
    return routes


def get_routes_fromid(routeids, table, source, connection, cur):
    string_list = list_to_string(routeids)
    try:
        sql_query = f"""SELECT *  FROM {table}
            WHERE route_id IN {string_list}
            AND source = {source}"""
        cur.execute(sql_query)
        connection.commit()
        routes_fetch = cur.fetchall()
        desc = cur.description
        column_names = [col[0] for col in desc]
        routes = pd.DataFrame(routes_fetch, columns=column_names)
        routes.set_index('route_id', inplace=True)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching routes/no routes available")
        raise error
    return routes


def separate_shift_idsx(routes):
    shifts = routes['shift'].max()
    shiftidx = {}
    for i in range(1, shifts+1):
        shiftidx[i] = routes.loc[
            routes['shift'] == i].index
    return shiftidx


def get_turnaround_time(site_id):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT turnaround_time, min_to_connect  FROM t_sites
            WHERE site_id={site_id}"""
        site_data = pd.read_sql_query(sql_query, cnx).iloc[0]
        turnaround = site_data['turnaround_time']
        min_to_connect = site_data['min_to_connect']
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching routes/no routes available")
        raise error
    finally:
        cnx.dispose()
    return turnaround, min_to_connect


def get_vehicle_specs(vehicles, connection, cur):
    try:
        sql_query = f"""SELECT spec_id, energy_use, battery_size, charge_power_ac, charge_power_dc,
            max_load, max_crate, fuel_type FROM t_vehicle_specification
            WHERE spec_id IN {tuple(vehicles)}"""
        cur.execute(sql_query)
        connection.commit()
        spec_array = cur.fetchall()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error getting vehicle specs")
        raise error
    specs = {}
    specs['pack'] = [spec_array[0][2], spec_array[-1][2]]
    specs['drive'] = [spec_array[0][1], spec_array[-1][1]]
    specs['rang'] = [specs['pack'][i]/specs['drive'][i] for i in range(2)]
    specs['payload'] = [spec_array[0][5] + DERROGATION,
                        spec_array[-1][5] + DERROGATION]
    specs['crates'] = [spec_array[0][6], spec_array[-1][6]]
    specs['fuel'] = [spec_array[0][7], spec_array[-1][7]]
    specs['max_charge_ac'] = [spec_array[0][3], spec_array[-1][3]]
    specs['max_charge_dc'] = [spec_array[0][4], spec_array[-1][4]]
    return specs


def calculate_IStps(end1, start2, connectdelta):
    """Calculates the number of potential intershift charging slots

    Args:
        end1 (DateTime): End of first route
        start2 (DateTime): Start of second route

    Returns:
        int: number of potential charging slots
    """
    num_tps = int((start2 - end1 - connectdelta)/TIME_INT_IS)
    return num_tps


def vehicleMatrix(journeys, N):
    df = pd.DataFrame(
        data={'allocated_vehicle_id': range(1, N+1)},
        index=range(1, N+1))
    df = df.merge(
            journeys.reset_index().set_index('allocated_vehicle_id'),
            left_index=True, right_index=True, how='left')
    df[['route_id', 'equivalent_mileage']] = df[[
        'route_id', 'equivalent_mileage']].fillna(0)
    df[['departure_time', 'arrival_time']] = df[[
        'departure_time', 'arrival_time']].fillna(
            dt.datetime(1900, 1, 1, 0))
    return df


def mergeJourneys(first, second, params, specs):
    df = pd.concat([first, second])

    dfmerged = df.groupby(['date', 'allocated_vehicle_id']).agg({
        'departure_time': 'min',
        'arrival_time': 'max',
        'distance_miles': 'sum',
        'payload': 'max',
        'number_crates': 'max',
        'equivalent_mileage': 'sum'
    })

    df_is = df.groupby(['date', 'allocated_vehicle_id']).agg({
        'departure_time': 'max',
        'arrival_time': 'min',
        'equivalent_mileage': 'last'
    })
    connectdelta = dt.timedelta(minutes=int(params['min_to_connect']))
    df_is['is_time'] = (df_is['departure_time'] - df_is['arrival_time']
                        - connectdelta)
    df_is['num_tps'] = (df_is['is_time']/TIME_INT_IS).astype(int).clip(lower=0)
    df_is['max_is_kwh'] = df_is['num_tps']*TP_FRACT_IS*params['charger2']
    drive = specs['drive'][0]
    df_is['max_is_miles'] = df_is['max_is_kwh']/drive
    dfmerged['equivalent_mileage'] = (
        dfmerged['equivalent_mileage']-df_is['max_is_miles']
        ).clip(lower=df_is['equivalent_mileage'])
    dfmerged.reset_index(inplace=True)
    dfmerged.index.rename('route_id', inplace=True)
    return dfmerged


def get_parameters(alloc):
    params = alloc.copy()
    # params['turnaround'], params['min_to_connect'] = get_turnaround_time(
    #     alloc['site_id'])
    return params


def solve_assignment(cost):
    """Optimisation process to assign best route/vehicle combinations

    Args:
        cost (DataFrame): costs for each vehicle/route combo

    Returns:
        (DataFrame): Vehicle assigned to each route + cost
        (score): score for each route
    """
    # TODO make into numpy arrays, and CVXPY
    routes = cost.index.get_level_values(0).unique()
    vehicles = cost.index.get_level_values(1).unique()
    cost_col = cost.columns[0]
    # Create our variable matrix
    assignment = pulp.LpVariable.dicts(
        "assign",
        ((route, vehicle) for route, vehicle in cost.index),
        cat='Binary')
    # Create PuLP problem
    shiftprob = pulp.LpProblem('Assigning_double_shifts_to_vehicles',
                               pulp.LpMaximize)
    # Add costs
    shiftprob += pulp.lpSum(
        [cost.loc[(route, vehicle), cost_col] * assignment[route, vehicle]
         for route, vehicle in cost.index]
    ), 'Feasibility_cost'

    # Only one vehicle per route constraint
    for route in routes:
        shiftprob += pulp.lpSum(
            [assignment[route, vehicle] for vehicle in vehicles]
        ) == 1

    # Max one route per vehicle
    for vehicle in vehicles:
        shiftprob += pulp.lpSum(
            [assignment[route, vehicle] for route in routes]
        ) <= 1

    # Solve and print to the screen
    shiftprob.solve(pulp.PULP_CBC_CMD(msg=False))
    # Get output variables
    assignments = []
    for route, vehicle in assignment:
        if shiftprob.status == 1:
            x = assignment[(route, vehicle)].varValue
        else:
            x = 0
        var_output = {
            'route_id': route,
            'allocated_vehicle_id': vehicle,
            'Feasible': x,
            'route_cost': cost.loc[(route, vehicle), cost_col]
        }
        assignments.append(var_output)
    df = pd.DataFrame.from_records(assignments)
    df = df[df['Feasible'] == 1]
    df.drop(columns='Feasible', inplace=True)
    df.set_index(['route_id'], inplace=True)
    return df


def cost_matrix(first, second, params, specs):
    """Calculates the cost for each journey/veh combination

    Args:
        dayJour (DataFrame): all journeys in a branch in a day
        N (int): number of vehicles available
        v (list): list of (string) vehicle types to use, in order of
            increasing pack capacity
        charger (list): list of (int) charger power to use in kW, in
            ascending order

    Returns:
        DataFrame: MultiIndex table of costs per combination.
            First index level is the route, second is the vehicle ID
            Single row is the cost
    """
    turndelta = dt.timedelta(minutes=int(params['turnaround']))
    connectdelta = dt.timedelta(minutes=int(params['min_to_connect']))
    M = len(second.index.unique())
    # specs = get_vehicle_specs([params['vehicle1'], params['vehicle2']],
    #                               connection, cur)
    # N = params['num_v_final']
    N = len(first)
    charger_ac = min(specs['max_charge_ac'] + [params['charger1']])
    charger_dc = min(specs['max_charge_dc'] + [params['charger2']])
    df = pd.DataFrame({
        'allocated_vehicle_id': np.repeat(
            np.array(first['allocated_vehicle_id']), M),
        'End_First': np.repeat(np.array(first['arrival_time']), M),
        'Mileage_First': np.repeat(np.array(first['equivalent_mileage']), M),
        'Payload_First': np.repeat(np.array(first['payload']), M),
        'Crates_First': np.repeat(np.array(first['number_crates']), M),
        'route_id': np.tile(np.array(second.index), N),
        'Start_Second': np.tile(np.array(second['departure_time']), N),
        'Mileage_Second': np.tile(np.array(second['equivalent_mileage']), N),
        'Payload_Second': np.tile(np.array(second['payload']), N),
        'Crates_Second': np.tile(np.array(second['number_crates']), N),
    })
    df['Total_Mileage'] = df['Mileage_First'] + df['Mileage_Second']
    df['Capacity_Large'] = (
        (df[['Payload_First', 'Payload_Second']].max(axis=1)
         <= specs['payload'][-1])
        & (df[['Crates_First', 'Crates_Second']].max(axis=1)
           <= specs['crates'][-1]))
    df['Capacity_Small'] = (
        (df[['Payload_First', 'Payload_Second']].max(axis=1)
         <= specs['payload'][0])
        & (df[['Crates_First', 'Crates_Second']].max(axis=1)
           <= specs['crates'][0]))
    df['IStps'] = df.apply(lambda row: calculate_IStps(
            row['End_First'], row['Start_Second'], connectdelta), axis=1)
    # Max possible amount of charge delivered
    df['IS_max0'] = (charger_ac * CHARGER_EFF
                     * TP_FRACT_IS * df['IStps'])
    df['IS_max1'] = (charger_dc * CHARGER_EFF
                     * TP_FRACT_IS * df['IStps'])
    df['Cost'] = -N
    # Possible with largest vehicle, no IS (0.5)
    df.loc[(df['End_First'] <= df['Start_Second'] - turndelta)
           & (df['Total_Mileage'] <= specs['rang'][-1])
           & (df['Capacity_Large']), 'Cost'] = 0.5
    # Possible with smallest pack, no IS (1)
    df.loc[(df['End_First'] <= df['Start_Second'] - turndelta)
           & (df['Total_Mileage'] <= specs['rang'][0])
           & (df['Capacity_Small']), 'Cost'] = 1
    # Slow IS required for largest pack (0.25-0.5)
    mask = ((df['End_First'] <= df['Start_Second'] - turndelta)
            & (df['Total_Mileage']*specs['drive'][1] > specs['pack'][1])
            & ((df['Total_Mileage']*specs['drive'][1] - df['IS_max0'])
               <= specs['pack'][1])
            & (df['Capacity_Large']))
    df.loc[mask, 'Cost'] = (0.5-0.25*(
        df['Total_Mileage']*specs['drive'][1] - specs['pack'][1])
                            / df['IS_max0'])
    # Fast IS required for largest pack (0-0.25)
    df.loc[(df['End_First'] <= df['Start_Second'] - turndelta)
           & (df['Total_Mileage']*specs['drive'][1]
              > specs['pack'][1] + df['IS_max0'])
           & ((df['Total_Mileage']*specs['drive'][1] - df['IS_max1'])
              <= specs['pack'][1])
           & (df['Capacity_Large']), 'Cost'] = (
               0.25 - 0.25 * (df['Total_Mileage']*specs['drive'][1]
                              - specs['pack'][1]) / df['IS_max1'])
    # Possible with smallest pack and slow IS (0.75-1)
    df.loc[(df['End_First'] <= df['Start_Second'] - turndelta)
           & (df['Mileage_First'] <= specs['rang'][0])
           & (df['Mileage_Second'] <= specs['rang'][0])
           & (df['Total_Mileage']*specs['drive'][0] > specs['pack'][0])
           & ((df['Total_Mileage']*specs['drive'][0] - df['IS_max0'])
              < specs['pack'][0])
           & (df['Capacity_Small']), 'Cost'] = (1-0.25*(
                  df['Total_Mileage']*specs['drive'][0]
                  - specs['pack'][0])/df['IS_max0'])
    # Possible with smallest pack and fast IS (0.5-0.75)
    df.loc[(df['End_First'] <= df['Start_Second'] - turndelta)
           & (df['Mileage_First'] <= specs['rang'][0])
           & (df['Mileage_Second'] <= specs['rang'][0])
           & (df['Total_Mileage']*specs['drive'][0]
              >= specs['pack'][0] + df['IS_max0'])
           & ((df['Total_Mileage']*specs['drive'][0] - df['IS_max1'])
              < specs['pack'][0])
           & (df['Capacity_Small']), 'Cost'] = (
               0.75-0.25*(df['Total_Mileage']*specs['drive'][0]
                          - specs['pack'][0])/df['IS_max1'])

    df.sort_values(by=['route_id', 'allocated_vehicle_id'], inplace=True)
    df.set_index(['route_id', 'allocated_vehicle_id'], inplace=True)
    return df[['Cost']]


def update_alloc(alloc, connection, cur):
    column_names = ['num_v_final']
    column_string = ", ".join([f"{c}={alloc[c]}" for c in column_names])
    try:
        sql_query = f"""UPDATE t_allocation
            SET {column_string}
            WHERE allocation_id={alloc['allocation_id']};"""
        cur.execute(sql_query)
        connection.commit()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updation t_allocation table")
        raise error
    return


def update_pairings(pairings, connection, cur):
    pairings_string = ", ".join(
        [str(tuple(e)) for e in pairings.reset_index().values])
    try:
        sql_query = f"""INSERT INTO t_route_allocated
            (route_id, allocated_vehicle_id, route_cost, allocation_id)
            VALUES {pairings_string}
            ON CONFLICT (route_id, allocation_id) DO UPDATE
                SET allocated_vehicle_id = excluded.allocated_vehicle_id,
                    route_cost = excluded.route_cost;"""
        cur.execute(sql_query)
        connection.commit()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updating t_route_allocated table")
        raise error
    return


def daily(date, alloc, connection, cur):
    # cnx = dbh.create_alch_engine()
    routes = get_daily_routes(date, alloc['allocation_id'], connection, cur)
    N = alloc['num_v_final']
    if len(routes) > 0:
        routes = get_daily_route_data(routes, alloc, connection, cur)
        shiftidx = separate_shift_idsx(routes)
        # Allocate the first shift journeys to vehicles
        M = len(shiftidx[1])
        # Bill
        shiftidx[1] = shiftidx[1].sort_values()
        routes.loc[shiftidx[1], 'allocated_vehicle_id'] = (range(1, M+1))
        params = alloc.copy()
        params['allocation_score'] = -1
        scorecap = -1
        specs = get_vehicle_specs([params['vehicle1'], params['vehicle2']],
                                  connection, cur)
        # If the score is negative, keep adding vehicles
        while max(params['allocation_score'], scorecap) < 0:
            logger.debug(f"{str(date)[:10]}, {N} vehicles")
            # shift_scores = {}
            allocation_results = {}
            first_routes = routes.loc[shiftidx[1]]
            # shift_scores[1] = 0
            cols = ['allocated_vehicle_id', 'route_cost']
            allocation_results[1] = first_routes[cols]
            nshifts = len(shiftidx)
            i = 2

            while nshifts - i > -1:  # Iterate over remaining shifts
                if len(shiftidx[i]) > 0:
                    # Bill
                    shiftidx[i] = shiftidx[i].sort_values()
                    vehicleMat = vehicleMatrix(first_routes, N)
                    pair_costs = cost_matrix(
                        vehicleMat, routes.loc[shiftidx[i]], params, specs)
                    allocation_results[i] = solve_assignment(pair_costs)
                    # if there are more shifts to assign, merge previous shifts
                    # and assing as firstjourneys
                    if nshifts > i:
                        secondJourneys = routes.loc[shiftidx[i]]
                        secondJourneys[cols] = allocation_results[i]
                        first_routes = mergeJourneys(
                            first_routes, secondJourneys, params, specs)
                i += 1
            pairings = pd.concat(allocation_results.values())
            params['allocation_score'] = pairings['route_cost'].min()
            if params['cap_vehicles']:  # If the number of vehicles is capped
                scorecap = 0  # Stops adding vehicles
            N += 1
        # Update num_v to the parameters table
        N += -1
        params['num_v_final'] = N
        update_alloc(params, connection, cur)
        # Update t_route_allocated with the new vehicle IDs and route_cost
        pairings['allocation_id'] = params['allocation_id']
        update_pairings(pairings, connection, cur)
    # cnx.dispose()
    return N


def list_to_string(python_list):
    if len(python_list) == 1:
        new_list = f"({python_list[0]})"
    else:
        new_list = str(tuple(python_list))
    return new_list


def find_unallocated_dates(alloc, connection, cur):
    try:
        sql_query = f"""SELECT DISTINCT date FROM t_route_allocated
            WHERE allocation_id={alloc}
            AND allocated_vehicle_id is Null
            ORDER BY date """
        cur.execute(sql_query)
        connection.commit()
        dates = cur.fetchall()
        dates = [date[0] for date in dates]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error getting unallocated dates")
        raise error
    return dates


def main(idx):
    # Iterate over dates and call daily allocation
    try:
        connection, cur = dbh.database_connection('test')
        # cnx = dbh.create_alch_engine()
        # run = rh.get_current_run(connection, cur)
        # Read the allocation inputs
        # alloc = find_current_allocation(cnx)
        alloc = get_allocation(idx, connection, cur)
        alloc['turnaround'], alloc['min_to_connect'] = get_turnaround_time(
            alloc['site_id'])
        # Get date range
        date_range = pd.date_range(alloc['start_date'], alloc['end_date']
                                   ).values
        for date in date_range[:]:
            try:
                alloc['num_v_final'] = daily(date, alloc, connection, cur)
            except Exception as e:
                logger.error(e)
    except Exception as e:
        logger.error(e)
        SystemExit(e)
    finally:
        cur.close()
        connection.close()
        logger.info("Closed db connection")
    return


def run_unallocated(idx):
    try:
        connection, cur = dbh.database_connection('test')
        cnx = dbh.create_alch_engine()
        alloc = get_allocation(idx, connection, cur)
        alloc['turnaround'], alloc['min_to_connect'] = get_turnaround_time(
            alloc['site_id'])
        # Get date range
        date_range = find_unallocated_dates(idx, connection, cur)
        print(idx, '# dates', len(date_range))
        for date in date_range:
            try:
                _ = daily(date, alloc, connection, cur)
            except Exception as e:
                logger.error(e)
    except Exception as e:
        logger.error(e)
        SystemExit(e)
    finally:
        cnx.dispose()
        cur.close()
        connection.close()
        logger.info("Closed db connection")
    return


if __name__ == '__main__':
    main()
    # run_unallocated(257)
