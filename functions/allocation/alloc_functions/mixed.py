# THIS MODULE ISN'T IN USE
# Everything that happens in mixed_journeys
# Adds entries (with new Scenario IDs and same allocation ID) to the
# journey_vehicle table#
# Exports stuff to summary scenario table
# Something sets the flag in t_run_allocation to Done at the end

import numpy as np
import pandas as pd
import os
import psycopg2
# import sqlalchemy
import datetime as dt
import json
import pipeline_plan_functions.utils.pipe_db_handler as dbh
import pipeline_plan_functions.utils.data_handler as dh
import alloc_functions.cleanup as cleaner
import alloc_functions.daily as adf
from python_utils.utils.logger import logger
logger.setLevel(os.getenv('log_level', "DEBUG"))

DEFAULT_DIESEL = 28
TIME_INT_IS = dt.timedelta(minutes=30)
N = int(dt.timedelta(days=1)/TIME_INT_IS)
POTENTIAL_TPS_IS = [i*TIME_INT_IS for i in range(N)]
CHARGER_EFF = 0.9
TP_FRACT = TIME_INT_IS/dt.timedelta(hours=1)
co = {
    'VEHID': 'allocated_vehicle_id',
    'DATE': 'date',
    'ENERGY': 'energy_required_kwh',
    'VAN': 'allocated_spec_id',
    'ROUTE': 'route_id',
    'DIESELF': 'diesel_fuel_consumption',
    'MILEAG': 'distance_miles'
}
DERROGATION = 725


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


def get_mixed_inputs(idx, connection, cur, cnx):
    # run = dh.get_current_run(connection, cur)
    # Get run input parameters
    # alloc = adf.find_current_allocation(cnx)
    alloc = get_allocation(idx, cnx)
    inputs = dh.get_inputs('t_run_allocation', alloc['run_id'],
                           connection, cur)
    alloc['mixed_fleet'] = json.loads(inputs['mixed_fleet'])
    # alloc['vehicle_pool'] = json.loads(alloc['vehicle_pool'])
    alloc['min_to_connect'] = adf.get_turnaround_time(alloc['site_id'])[1]
    return alloc


def select_vehicles(vehicle_list, inputs, connection, cur):
    vehicles = []
    diesel_vans = get_diesel_vans(connection, cur)
    if vehicle_list == ['s', 'l']:
        sorted_vehicles = inputs['vehicle_pool'][0] + inputs['vehicle_pool'][1]
        large = sorted_vehicles.index(inputs['vehicle2'])
        smallervans = sorted_vehicles[:large]
        vehicles = [[smallvan, inputs['vehicle2']] for smallvan in smallervans]
    elif len(set(vehicle_list) & set(diesel_vans)) == 0:
        vehicles = [vehicle_list + [DEFAULT_DIESEL]]
    else:
        vehicles = [vehicle_list]
    return vehicles


def get_diesel_vans(connection, cur):
    try:
        sql_query = ("SELECT spec_id FROM t_vehicle_specification "
                     "WHERE fuel_type IN ('petrol', 'diesel')")
        cur.execute(sql_query)
        connection.commit()
        diesel_vehicles = cur.fetchall()
        diesel_ids = [vehicle[0] for vehicle in diesel_vehicles]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error getting diesel vehicle IDs")
        raise error
    return diesel_ids


def group_routes(routes):
    groupedJ = routes.groupby(['date', 'allocated_vehicle_id']).agg({
        'distance_miles': 'sum',
        'payload': 'max',
        'number_crates': 'max',
        'arrival_time': 'max',
        'departure_time': 'min',
        'category': 'count',
        # co['DURAT']: 'sum',
        'equivalent_mileage': 'sum',
    })
    groupedJ[['IndMileage']] = routes.groupby(
        ['date', 'allocated_vehicle_id']).agg({'equivalent_mileage': 'max'})
    groupedJ.rename(columns={'category': 'NRoutes'}, inplace=True)
    groupedJ['route_date'] = groupedJ.index.get_level_values('date')
    return groupedJ


def tp_journeys(route, turn):
    """Calculates unavailable time periods and return time of a route

    Args:
        route (int): route id
        turn (int): minutes to connect

    Returns:
        series: availability of the vehicle for each time period. True when
            vehicle is unable to charge
        index: index of vehicle profile when it returns to depot
    """
    turndelta = dt.timedelta(minutes=int(turn))
    tps = np.array(POTENTIAL_TPS_IS)
    after_departure = tps > (route['departure_time'] - route['date']
                             - TIME_INT_IS)
    before_return = tps < (route['arrival_time'] - route['date'] + turndelta)
    return ~(after_departure & before_return)


def get_vehicle_dict(vehicles, cnx):
    try:
        sql_query = f"""SELECT spec_id, energy_use, battery_size, charge_power_ac, charge_power_dc,
            max_load, max_crate, fuel_type FROM t_vehicle_specification
            WHERE spec_id IN {tuple(vehicles)}"""
        spec_dict = pd.read_sql_query(sql_query, cnx, index_col='spec_id')
    except (Exception, psycopg2.Error) as error:
        logger.error("Error getting vehicle specs")
        raise error
    return spec_dict.to_dict(orient='index')


def rearrange_mixed(grouped, v):
    L = 0  # Number of vehicle-duties assigned to larger vans
    vDict = {}
    groupedJ = grouped.copy()
    vehicleIDs = groupedJ.index.get_level_values('allocated_vehicle_id'
                                                 ).unique()
    nV = len(vehicleIDs)
    dates = groupedJ.index.get_level_values('date').unique()
    groupedJ['NewVehicleID'] = 0
    for i in range(1, len(v)+1):
        veh = v[-i]
        smallerv = v[:-i]
        # If that vehicle is required
        van_duties = groupedJ[groupedJ['allocated_spec_id'] == veh]
        if len(van_duties) > 0:
            # Minimum number of those vans required
            M = van_duties.groupby('date').count()[
                'distance_miles'].max()
            print(i, 'Vehicle:', veh, '\nSmaller vehicles:', smallerv,
                  '\nNumber of vehicles:', M)
            smallN = nV - L - M   # Number of vehicles with smaller vans
            vDict[veh] = vehicleIDs[-M-L:][:M]
            if smallN >= 0:
                # Rearrange vehicles
                for date in dates:
                    dayJ = groupedJ.loc[date]
                    # Calculate how many duties are currently assigned to
                    # smaller vehicles
                    smallerduties = dayJ[dayJ['allocated_spec_id'
                                              ].isin(smallerv)].index
                    oldLarge = dayJ[dayJ['allocated_spec_id'] == veh].index
                    # Calculate how many journeys need to move
                    move = max(len(smallerduties)-smallN, 0)
                    newLarge = dayJ.loc[smallerduties].sort_values(
                        by='distance_miles', ascending=False).index[:move]
                    # Assign those duties to the vehicle in play
                    groupedJ.loc[(date, newLarge), 'allocated_spec_id'] = veh
                    vehDuties = list(oldLarge) + list(newLarge)
                    n_duties = len(vehDuties)
                    groupedJ.loc[(date, vehDuties), 'NewVehicleID'
                                 ] = vDict[veh][:n_duties]
                L += M
    return groupedJ, vDict


def grouped_mixed_fleet(journeys, v, ch, turn, specs):
    fastch = max(ch)
    groupedJ = group_routes(journeys)
    for idx in groupedJ.index:
        masklist = []
        dutyR = journeys[(journeys['date'] == idx[0])
                         & (journeys['allocated_vehicle_id'] == idx[1])].index
        # Calculate IS shifts
        for r in dutyR:
            masklist.append(tp_journeys(journeys.loc[r], turn))
        masklist.append(np.array(POTENTIAL_TPS_IS)
                        > (groupedJ.loc[idx, 'departure_time']
                           - groupedJ.loc[idx, 'route_date']))
        masklist.append(np.array(POTENTIAL_TPS_IS)
                        < (groupedJ.loc[idx, 'arrival_time']
                           - groupedJ.loc[idx, 'route_date']))
        n = len(masklist)
        tps = np.sum(np.vstack(masklist).sum(axis=0) == n)
        groupedJ.loc[idx, 'TPs'] = tps
        feas = False
        i = 0
        # Calculate minimum vehicle required
        while feas is False:
            # print('v:', v, 'i:', i)
            veh = v[i]
            energy_req = (
                groupedJ.loc[idx, 'equivalent_mileage']
                * specs[veh]['energy_use'])
            ind_energy_req = (
                groupedJ.loc[idx, 'IndMileage'] * specs[veh]['energy_use'])
            isMax = fastch * CHARGER_EFF * TP_FRACT * tps
            volweight = (
                (groupedJ.loc[idx, 'payload']
                 <= specs[veh]['max_load'] + DERROGATION)
                & (groupedJ.loc[idx, 'number_crates']
                   <= specs[veh]['max_crate']))
            feasibility_mask = (
                (energy_req - isMax < specs[veh]['battery_size'])
                & (ind_energy_req < specs[veh]['battery_size'])
                & volweight)
            if feasibility_mask:
                feas = True
                groupedJ.loc[idx, 'allocated_spec_id'] = veh
            i += 1
    groupedJ, vDict = rearrange_mixed(groupedJ, v)
    groupedJ['energy_required_kwh'] = (
            groupedJ['equivalent_mileage']
            * groupedJ['allocated_spec_id'].map(specs).apply(pd.Series)[
                'energy_use'])
    # Calculate charger requirements
    groupedJ['ISCharger'] = -1
    groupedJ['ChargingH'] = (
        dt.timedelta(hours=29)
        - (groupedJ['arrival_time']-groupedJ['route_date'])
        - dt.timedelta(minutes=int(turn))
        ).dt.total_seconds()/3600
    # Calculate energy used and charging speed
    groupedJ['Clip'] = groupedJ['allocated_spec_id'].map(specs).apply(
        pd.Series)['battery_size']
    groupedJ['EnergyClip'] = groupedJ['energy_required_kwh'].clip(
        upper=groupedJ['Clip'])
    groupedJ['Rate_kW'] = (
        groupedJ['EnergyClip'] / (groupedJ['ChargingH'] * CHARGER_EFF))
    groupedJ['ONCharger'] = 0
    groupedJ.loc[groupedJ['Rate_kW'] <= ch[-1], 'ONCharger'] = ch[-1]
    groupedJ.loc[groupedJ['Rate_kW'] <= ch[0], 'ONCharger'] = ch[0]
    groupedJ['IS_Rate'] = (
        (groupedJ['energy_required_kwh'] - groupedJ['EnergyClip'])
        / (TP_FRACT * groupedJ['TPs']) * CHARGER_EFF).fillna(0)
    ch_long = [0] + ch
    for i in range(1, 1 + len(ch_long)):
        groupedJ.loc[groupedJ['IS_Rate'] <= ch_long[-i],
                     'ISCharger'] = ch_long[-i]
    return groupedJ, vDict


def fix_journeys_mixed(journeys1, groupedJ, specs, connection, cur):
    if co['VAN'] in journeys1.columns:
        journeys1.drop(columns=co['VAN'], inplace=True)
    journeys = journeys1.merge(groupedJ[[co['VAN'], 'NewVehicleID']],
                               left_on=['date', co['VEHID']],
                               right_index=True)
    journeys['Old_VID'] = journeys[co['VEHID']]
    journeys[co['VEHID']] = journeys['NewVehicleID']
    # journeys[co['DAT']] = pd.to_datetime(
    #     journeys[co['DATE']]).dt.date
    journeys.sort_values(by=['date', co['ROUTE']], inplace=True)
    journeys.reset_index(inplace=True)
    journeys.set_index(['date', co['ROUTE']], inplace=True)
    journeys[co['ENERGY']] = (
            journeys['equivalent_mileage']
            * journeys[co['VAN']].map(specs).apply(pd.Series)['energy_use'])
    journeys[['Diesel_Miles', co['DIESELF']]] = (0, 0)
    journeys['EV_Miles'] = journeys[co['MILEAG']]
    diesel_vans = get_diesel_vans(connection, cur)
    diesel_mask = journeys[co['VAN']].isin(diesel_vans)
    if diesel_mask.sum() > 0:
        journeys.loc[diesel_mask, co['DIESELF']] = journeys.loc[diesel_mask,
                                                                co['ENERGY']]
        journeys.loc[diesel_mask, co['ENERGY']] = 0
        journeys.loc[diesel_mask, 'Diesel_Miles'] = journeys.loc[
            diesel_mask, 'EV_Miles']
        journeys.loc[diesel_mask, 'EV_Miles'] = 0
    journeys.drop(columns=['NewVehicleID'], inplace=True)
    return journeys


def count_chargers(groupedJ, ch):
    cReqs = groupedJ.groupby([co['DATE'], 'ISCharger']).count()[
        co['ENERGY']].reset_index('ISCharger')
    cf, cs = (0, 0)
    if len(cReqs[cReqs['ISCharger'] == ch[-1]]) > 0:
        cf = cReqs[cReqs['ISCharger'] == ch[-1]][co['ENERGY']].max()
    if len(cReqs[cReqs['ISCharger'] == ch[0]]) > 0:
        cs = cReqs[cReqs['ISCharger'] == ch[0]][co['ENERGY']].max()
    # Count overnight fast chargers
    cReqs = groupedJ.groupby([co['DATE'], 'ONCharger']).count()[
        co['ENERGY']].reset_index('ONCharger')
    cf2 = 0
    if len(cReqs[cReqs['ONCharger'] == ch[-1]]) > 0:
        cf2 = cReqs[cReqs['ONCharger'] == ch[-1]][co['ENERGY']].max()
    errorON = len(groupedJ[groupedJ['ONCharger'] == 0])
    errorIS = len(groupedJ[groupedJ['ISCharger'] == -1])
    return (cs, cf, cf2, errorON, errorIS)


def vehicle_fuel_category(fuels):
    fossil_fuel = [fuel in ['diesel', 'petrol'] for fuel in fuels]
    if all(fossil_fuel):
        return 'Fossil Fuel'
    elif any(fossil_fuel):
        return 'Mixed'
    else:
        return 'EV'


def get_fps_allocation_id(connection, cur):
    '''Return the largest currently assigned fps allocation id'''
    # establish FPS database connection
    query_str = ('SELECT allocation_id FROM t_allocation ORDER BY '
                 'allocation_id DESC LIMIT 1')
    allocation_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        allocation_id = cur.fetchall()[0][0]
    except Exception:
        logger.info('No node ID in t_telematics')
    return allocation_id


def upload_mixed_routes(routes, cnx):
    cols = ['allocated_vehicle_id', 'route_id', 'energy_required_kwh',
            'diesel_fuel_consumption', 'allocation_id', 'date', 'shift',
            'route_cost', 'allocated_spec_id']
    try:
        routes.reset_index()[cols].to_sql('t_route_allocated', con=cnx,
                                          if_exists='append', index=False)
        logger.debug("Uploaded mixed fleet routes to t_route_allocated")
    except (Exception, psycopg2.Error) as error:
        logger.error("Couldn't update mixed fleet routes")
        logger.error(error)
        raise error
    return


def complete_alloc(allocation_id, connection, cur):
    try:
        sql_query = f"""UPDATE t_allocation SET allocated='c'
            WHERE allocation_id={allocation_id};"""
        cur.execute(sql_query)
        connection.commit()
        logger.debug("Updated t_allocation to completed")
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updating t_allocation table")
        raise error
    return


def main(idx):
    try:
        connection, cur = dbh.database_connection('test')
        cnx = dbh.create_alch_engine()
        # FIND THE MOST UP TO DATE RUN ID
        # run = dh.get_current_run(connection, cur)
        # Get mixed spec setting from t_run_allocation
        alloc = get_mixed_inputs(idx, connection, cur, cnx)
        routes = cleaner.get_allocated_routes(
            alloc['allocation_id'], connection, cur)
        routes = cleaner.get_daily_route_data(
            routes, alloc, connection, cur)
        # For each spec
        # mixed_specs = alloc['mixed_fleet'][0]
        for mixed_specs in alloc['mixed_fleet']:
            ch = mixed_specs[1]
            vehicles = select_vehicles(mixed_specs[0], alloc, connection, cur)
            all_vehicles = list(set(
                [item for sublist in vehicles for item in sublist]))
            veh_specs = get_vehicle_dict(all_vehicles, cnx)
            for v in vehicles:
                # idx = str(idx0) + '.' + str(j+1)
                groupedJ, dictV = grouped_mixed_fleet(
                    routes, v, ch, alloc['min_to_connect'], veh_specs)
                journeys2 = fix_journeys_mixed(
                    routes, groupedJ, veh_specs, connection, cur)
                r = count_chargers(groupedJ, ch)
                fast_ch = max(r[1], r[2])
                # v is all the vehicles considered, v2 is the vehicles
                # actually used
                v2 = [veh for veh in v if veh in dictV.keys()]
                n_veh = [len(dictV[veh]) for veh in v2]
                N = sum(n_veh)
                # n_char = [N-fast_ch, fast_ch]
                newalloc = alloc.copy()
                newalloc['original_allocation'] = newalloc.pop('allocation_id')
                newalloc['charger1'] = ch[0]
                newalloc['charger2'] = ch[-1]
                newalloc['vehicle_pool'] = str(v)
                newalloc['vehicle1'] = v2[0]
                newalloc['vehicle2'] = v2[-1]
                newalloc['num_vehicle1'] = min(n_veh[0], N-n_veh[-1])
                newalloc['num_vehicle2'] = n_veh[-1]
                newalloc['num_charger2'] = fast_ch
                newalloc['num_charger1'] = N - fast_ch
                fuels = [veh_specs[veh]['fuel_type'] for veh in v2]
                newalloc['vcategory'] = vehicle_fuel_category(fuels)
                newalloc['allocation_score'] = r[4]
                newalloc['overnight_error'] = r[3]
                newalloc['allocation_id'] = (
                    get_fps_allocation_id(connection, cur) + 1)
                newalloc['allocated'] = "c"
                del(newalloc['mixed_fleet'], newalloc['min_to_connect'])
                # Create new allocation entry
                pd.DataFrame(newalloc, index=[0]).to_sql(
                    't_allocation', con=cnx, if_exists='append', index=False)
                journeys2['allocation_id'] = newalloc['allocation_id']
                # Upload pairing table to database
                upload_mixed_routes(journeys2, cnx)
        complete_alloc(alloc['allocation_id'], connection, cur)
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
    main(114)
