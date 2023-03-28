# Equivalent to clean_results
# Clean results from staging table and export results to database, tagged by
# an allocation ID. Rearranges vehicle IDs
# Exports stuff to a summary scenario table
# Create a list of inputs for the mixed analysis and triggers it via bus. Adds
# a finish trigger to the end of the queue

import pandas as pd
import os
import psycopg2
import datetime as dt
import json
import pipeline_plan_functions.utils.pipe_db_handler as dbh
# import pipeline_plan_functions.utils.data_types as dth
# import pipeline_plan_functions.utils.data_handler as rh
import alloc_functions.daily as adf
from python_utils.utils.logger import logger
logger.setLevel(os.getenv('log_level', "DEBUG"))

SCHEDULE_CHARGE_DEFAULT = 1


def get_allocated_routes(allocation_id, connection, cur):
    try:
        sql_query = f"""SELECT *  FROM t_route_allocated
            WHERE allocation_id={allocation_id}"""
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


def get_allocation(idx):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT * FROM t_allocation WHERE allocation_id={idx}
                ORDER BY allocation_id ASC """
        allocations = pd.read_sql_query(sql_query, cnx)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching allocation table")
        raise error
    finally:
        cnx.dispose()
    current_allocation = allocations.iloc[0].to_dict()
    current_allocation['vehicle_pool'] = json.loads(
        current_allocation['vehicle_pool'])
    logger.debug(
        f"Current allocation ID: {current_allocation['allocation_id']}")
    return current_allocation


def get_daily_route_data(routes, params, connection, cur):
    # Fetch the original route data required and merges it all together
    orig_routes = adf.get_routes_fromid(routes.index, params['route_table'],
                                        params['source'], connection, cur)
    route_cols = ['departure_time', 'arrival_time', 'distance_miles',
                  'payload', 'number_crates', 'site_id_start',
                  'site_id_end']
    routes = routes.merge(orig_routes[route_cols], left_index=True,
                          right_index=True)
    routes['equivalent_mileage'] = routes['distance_miles'] / params['xmpg']
    routes['payload'] = routes['payload'].astype(float)
    return routes


def summariseResults(journeys2, alloc, connection, cur):
    params = alloc.copy()
    journeys = journeys2[journeys2['route_cost'] >= 0].copy()
    # journeys[co['DAT']] = pd.to_datetime(
    #     journeys[co['DATE']]).dt.date
    journeys.drop(columns='allocated_spec_id', inplace=True)
    specs = adf.get_vehicle_specs([params['vehicle1'], params['vehicle2']],
                                  connection, cur)
    journeys.loc[(journeys['shift'] == 1)
                 & (journeys['equivalent_mileage'] <= specs['rang'][-1])
                 & (journeys['payload'] <= specs['payload'][-1])
                 & (journeys['number_crates'] <= specs['crates'][-1]),
                 'route_cost'] = 0.5
    journeys.loc[(journeys['shift'] == 1)
                 & (journeys['equivalent_mileage'] <= specs['rang'][0])
                 & (journeys['payload'] <= specs['payload'][0])
                 & (journeys['number_crates'] <= specs['crates'][0]),
                 'route_cost'] = 1
    params['allocation_score'] = min(journeys['route_cost'])  # bad if negative
    vJourneys = (journeys.groupby(['date', 'allocated_vehicle_id'])
                 .agg({'departure_time': 'min',
                       'arrival_time': 'max',
                       'equivalent_mileage': 'sum',
                       'shift': 'count',
                       'route_cost': 'min',
                       'payload': 'max',
                       'number_crates': 'max'}))
    vJourneys['route_date'] = vJourneys.index.get_level_values('date')
    dates = vJourneys['route_date'].unique()
    v = [params['vehicle1'], params['vehicle2']]
    ch = [params['charger1'], params['charger2']]
    vJourneys['allocated_spec_id'] = params['vehicle2']
    vJourneys['Count'] = 1
    vJourneys.loc[vJourneys['route_cost'] > 0.5,
                  'allocated_spec_id'] = params['vehicle1']
    vJourneys.loc[
        (vJourneys['route_cost'] == 0)
        & (vJourneys['equivalent_mileage'] <= specs['rang'][0]),
        'allocated_spec_id'] = params['vehicle1']
    # Calculates number of vehicles required
    vReqs = vJourneys.groupby(['date', 'allocated_spec_id']).sum()[[
        'Count']].reset_index('allocated_spec_id')
    dayReqs = vReqs.groupby('date').sum()
    N = dayReqs['Count'].max()
    M = 0
    if len(vReqs[vReqs['allocated_spec_id'] == params['vehicle2']]) > 0:
        M = vReqs[vReqs['allocated_spec_id'] == params['vehicle2']
                  ]['Count'].max()
    smallN = N-M
    # Rearrange vehicles
    for date in dates:
        dayJ = vJourneys.loc[date]
        move = max(len(dayJ[dayJ['allocated_spec_id'] == v[0]]) - smallN, 0)
        newLarge = dayJ[dayJ['allocated_spec_id'] == v[0]].sort_values(
            by='equivalent_mileage', ascending=False).index[:move]
        vJourneys.loc[(date, newLarge), 'allocated_spec_id'] = v[-1]
        dayJ = vJourneys.loc[date]
        smallidx = dayJ[dayJ['allocated_spec_id'] == v[0]].index
        largeidx = dayJ[dayJ['allocated_spec_id'] == v[-1]].index
        vJourneys.loc[(date, smallidx), 'new_vehicle_id'] = range(
            1, len(smallidx)+1)
        vJourneys.loc[(date, largeidx), 'new_vehicle_id'] = range(
            smallN+1, smallN+len(largeidx)+1)
    journeys = journeys.merge(
        vJourneys[['allocated_spec_id', 'new_vehicle_id']],
        left_on=['date', 'allocated_vehicle_id'],
        right_index=True)

    journeys['Old_VID'] = journeys['allocated_vehicle_id']
    journeys['allocated_vehicle_id'] = journeys['new_vehicle_id']
    journeys.sort_values(by=['date', 'route_id'], inplace=True)
    journeys.reset_index(inplace=True)
    journeys.set_index(['date', 'route_id'], inplace=True)
    drive_dict = {v[i]: specs['drive'][i] for i in range(2)}
    journeys['energy_required_kwh'] = (
        journeys['equivalent_mileage']
        * journeys['allocated_spec_id'].map(drive_dict))
    # journeys[['Diesel_Miles', co['DIESELF']]] = (0, 0)
    # journeys['EV_Miles'] = journeys[co['MILEAG']]
    fuel_dict = {v[i]: specs['fuel'][i] for i in range(2)}
    diesel_mask = journeys['allocated_spec_id'].map(fuel_dict).isin(['petrol',
                                                                     'diesel'])
    if diesel_mask.sum() > 0:
        journeys.loc[diesel_mask, 'diesel_fuel_consumption'] = journeys.loc[
            diesel_mask, 'energy_required_kwh']
        journeys.loc[diesel_mask, 'energy_required_kwh'] = 0
        # journeys.loc[diesel_mask, 'Diesel_Miles'] = journeys.loc[diesel_mask,
        #                                                         'EV_Miles']
        # journeys.loc[diesel_mask, 'EV_Miles'] = 0
    journeys.drop(columns=['new_vehicle_id'], inplace=True)

    # Calculate number of chargers required
    vJourneys['ISCharger'] = 0
    vJourneys['ChargingH'] = (
        dt.timedelta(hours=31)
        - (vJourneys['arrival_time'] - vJourneys['route_date'])
        ).dt.total_seconds()/3600
    # Calculate energy used and charging speed
    vJourneys['EqMileageClip'] = vJourneys['equivalent_mileage'].clip(
        upper=specs['rang'][1])
    vJourneys['Rate_kW'] = (
        vJourneys['EqMileageClip']
        * vJourneys['allocated_spec_id'].map(drive_dict)
        / (vJourneys['ChargingH'] * adf.CHARGER_EFF))
    diesel_mask = vJourneys['allocated_spec_id'].map(fuel_dict).isin(
        ['petrol', 'diesel'])
    vJourneys.loc[diesel_mask, 'Rate_kW'] = 0
    vJourneys['ONCharger'] = 0
    vJourneys.loc[vJourneys['Rate_kW'] <= ch[-1], 'ONCharger'] = ch[-1]
    vJourneys.loc[vJourneys['Rate_kW'] <= ch[0], 'ONCharger'] = ch[0]
    vJourneys.loc[diesel_mask, 'ONCharger'] = 0
    for c in [0.25, 0.75]:
        vJourneys.loc[(vJourneys['route_cost'] > c)
                      & (vJourneys['route_cost'] < c+0.25),
                      'ISCharger'] = ch[0]
        vJourneys.loc[(vJourneys['route_cost'] < c)
                      & (vJourneys['route_cost'] > c-0.25),
                      'ISCharger'] = ch[-1]

    # Count intershift chargers
    cReqs = vJourneys.groupby(['date', 'ISCharger']).sum()[
        ['Count']].reset_index('ISCharger')
    # cf, cs, c0 = (0, 0, 0)
    cf, _ = (0, 0)
    if len(cReqs[cReqs['ISCharger'] == ch[-1]]['Count']) > 0:
        cf = cReqs[cReqs['ISCharger'] == ch[-1]]['Count'].max()
    # if len(cReqs[cReqs['ISCharger'] == ch[0]]['Count']) > 0:
    #     cs = cReqs[cReqs['ISCharger'] == ch[0]]['Count'].max()
    # Count overnight fast chargers
    cReqs = vJourneys.groupby(['date', 'ONCharger']).sum()[
        ['Count']].reset_index('ONCharger')
    cf2 = 0
    if len(cReqs[cReqs['ONCharger'] == ch[-1]]) > 0:
        cf2 = cReqs[cReqs['ONCharger'] == ch[-1]]['Count'].max()
    ONchargers = vJourneys[~diesel_mask]['ONCharger']
    params['overnight_error'] = len(ONchargers[ONchargers == 0])
    params['num_vehicle1'] = smallN
    params['num_vehicle2'] = M
    params['num_charger2'] = max(cf, cf2)
    params['num_charger1'] = N - params['num_charger2']
    params['schedule_charge'] = SCHEDULE_CHARGE_DEFAULT
    # params['allocated'] = "'a'"
    fossil_fuel = [fuel in ['diesel', 'petrol'] for fuel in specs['fuel']]
    if all(fossil_fuel):
        params['vcategory'] = "'Fossil Fuel'"
        params['num_charger1'] = 0
        params['num_charger2'] = 0
    elif any(fossil_fuel):
        params['vcategory'] = "'Mixed'"
        params['num_charger1'] = max(0, N - params['num_charger2']
                                     - params['vehicle2'])
    else:
        params['vcategory'] = "'EV'"
    return params, journeys


def update_pairings(routes, connection, cur):
    cols = ['allocation_id', 'allocated_vehicle_id', 'energy_required_kwh',
            'diesel_fuel_consumption', 'route_cost', 'allocated_spec_id']
    routes_toupdate = routes.droplevel('date')[cols]
    routes_toupdate['diesel_fuel_consumption'] = routes_toupdate[
        'diesel_fuel_consumption'].fillna(0)
    pairings_string = ", ".join([str(tuple(e)) for e
                                 in routes_toupdate.reset_index().values])
    try:
        sql_query = f"""INSERT INTO t_route_allocated (route_id, allocation_id,
            allocated_vehicle_id, energy_required_kwh,
            diesel_fuel_consumption, route_cost, allocated_spec_id)
            VALUES {pairings_string}
            ON CONFLICT (route_id, allocation_id) DO UPDATE
                SET allocated_vehicle_id = excluded.allocated_vehicle_id,
                    energy_required_kwh = excluded.energy_required_kwh,
                    diesel_fuel_consumption = excluded.diesel_fuel_consumption,
                    route_cost = excluded.route_cost,
                    allocated_spec_id = excluded.allocated_spec_id"""
        cur.execute(sql_query)
        connection.commit()
        logger.debug("Updated t_route_allocated with cleaned allocations")
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updating t_allocation table")
        raise error
    return


def update_alloc(alloc, connection, cur):
    column_names = ['allocation_score', 'num_vehicle1', 'num_vehicle2',
                    'num_charger1', 'num_charger2', 'vcategory',
                    'overnight_error', 'schedule_charge']
    column_string = ", ".join([f"{c}={alloc[c]}" for c in column_names])
    try:
        sql_query = f"""UPDATE t_allocation
            SET allocated='c', {column_string}
            WHERE allocation_id={alloc['allocation_id']};"""
        cur.execute(sql_query)
        connection.commit()
        logger.debug("Updated t_allocation with scores, etc")
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updation t_allocation table")
        raise error
    return


def main(idx):
    # Iterate over dates and call daily allocation
    try:
        connection, cur = dbh.database_connection('test')
        # cnx = dbh.create_alch_engine()
        # alloc = adf.find_current_allocation(cnx)
        alloc = get_allocation(idx)
        routes = get_allocated_routes(alloc['allocation_id'], connection, cur)
        routes = get_daily_route_data(routes, alloc, connection, cur)
        alloc, routes = summariseResults(
            routes, alloc, connection, cur)
        update_alloc(alloc, connection, cur)
        update_pairings(routes, connection, cur)
    except Exception as e:
        logger.error(e)
        SystemExit(e)
    finally:
        cur.close()
        connection.close()
        logger.info("Closed db connection")
    return


if __name__ == '__main__':
    main()