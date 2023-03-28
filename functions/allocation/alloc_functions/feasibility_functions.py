import numpy as np
import pandas as pd
import datetime as dt
import psycopg2
import pipeline_plan_functions.utils.pipe_db_handler as dbh
from python_utils.utils.logger import logger
import alloc_functions.cleanup as cleaner
import alloc_functions.mixed as mixed
import alloc_functions.controller as acf
import matplotlib.pyplot as plt
import matplotlib
import matplotlib.dates as mdates

TIME_INT_IS = dt.timedelta(minutes=30)
CHARGER_EFF = 0.9
TP_FRACT_IS = TIME_INT_IS/dt.timedelta(hours=1)
TURN = 5  # minutes
N = int(dt.timedelta(days=1)/TIME_INT_IS)
POTENTIAL_TPS_IS = [i*TIME_INT_IS for i in range(N)]
XMPG = 0.8
FPS_COLOURS = ['#004A9C', '#45D281', '#FEC001', '#A365E0', '#5B9BD5',
               '#FF0000', '#0563C1', '#954F72']


def add_scenario(scenario_values, connection, cur):
    """Creates a new entry in the charging scenario table"""
    try:
        sql_query = f"""INSERT INTO t_charging_scenarios
            (scenario_id, allocation_id, run_id, smart_charging, output_kwh,
            charger1, charger2, num_charger1, num_charger2)
            VALUES {scenario_values}"""
        cur.execute(sql_query)
        connection.commit()
        logger.debug(f"Added scenario {scenario_values[0]} to table")
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updating scenario table")
        raise error
    return


def create_allocation_table(inputs, sites, specs, connection):
    cur = connection.cursor()
    alloc_cols = [
        'run_id', 'allocation_id', 'start_date', 'end_date',
        'xmpg_change', 'vehicle_pool', 'charger1', 'charger2', 'route_table',
        'source']
    df = pd.DataFrame(
        columns=alloc_cols,
        index=pd.MultiIndex.from_product([sites, specs],
                                         names=['site_id', 'vehicle1']))
    df.reset_index(inplace=True)
    for c in ['run_id', 'start_date', 'end_date', 'xmpg_change', 'route_table',
              'cap_vehicles', 'source']:
        df[c] = inputs[c]
    largest_allocation_id = acf.get_fps_allocation_id(connection, cur)
    cur.close()
    df['allocation_id'] = df.index + largest_allocation_id + 1
    df['charger1'], df['charger2'] = (9, 9)
    df['allocated'] = 'n'
    df['vehicle2'] = df['vehicle1']
    return df


def q75(x):
    return x.quantile(0.75)


def q25(x):
    return x.quantile(0.25)


def q95(x):
    return x.quantile(0.95)


def q05(x):
    return x.quantile(0.05)


def edge_routes(routes):
    """Finds the first and last route for a vehicle
    """
    end_routes = routes.groupby('vehicle_id').agg({
        'departure_time': ['min', 'max']})
    end_routes = pd.concat([end_routes[('departure_time', 'min')],
                            end_routes[('departure_time', 'max')]])
    end_routes = pd.DataFrame(end_routes, columns=['date_edge'])
    end_routes['edge_routes'] = True
    end_routes = end_routes.reset_index()
    return end_routes.drop_duplicates()


def routes_from_veh(routes, vehicle,
                    start_dt=dt.datetime(1900, 1, 1),
                    end_dt=dt.datetime(2100, 1, 1)):
    """Finds the routes for a vehicle in a given time period
    """
    mask_vehicle = routes['vehicle_id'] == vehicle
    mask_start = routes['departure_time'] >= start_dt
    mask_end = routes['arrival_time'] < end_dt
    return routes[mask_vehicle & mask_start & mask_end]


def find_allocation(idx):
    """Find the allocation data based on allocation ID"""
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT * FROM t_allocation WHERE allocation_id={idx}
            LIMIT 1"""
        current_allocation = pd.read_sql_query(
            sql_query, cnx).iloc[0].to_dict()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching current allocation")
        raise(error)
    finally:
        cnx.dispose()
    return current_allocation


def group_routes(routes):
    """Group routes into daily vehicle duties
    """
    daily_duties = routes.groupby(['duty_id']).agg({
        'departure_time': 'min',
        'site_id_start': ['first', 'nunique'],
        'distance_miles': 'sum',
        'duration_hours': 'sum',
        'arrival_time': 'max',
        'allocation_id': 'count',
        'site_id_end': 'last',
        'allocated_spec_id': 'mean',
        'allocated_vehicle_id': 'mean',
        'date': 'first',
        'start_time': 'min',
        'end_time': 'max'})
    daily_duties.columns = [
        'departure_time', 'site_id_start', 'number_sites', 'distance_miles',
        'route_hours', 'arrival_time', 'n_routes', 'site_id_end',
        'allocated_spec_id', 'allocated_vehicle_id', 'date', 'start_time',
        'end_time']
    daily_duties['same_return'] = (daily_duties['site_id_start']
                                   == daily_duties['site_id_end'])
    daily_duties['duty_duration'] = (
        daily_duties['arrival_time'] - daily_duties['departure_time']
        ).dt.total_seconds()/3600
    daily_duties[['ind_mileage']] = routes.groupby(
        ['duty_id']).agg({'distance_miles': 'max'})
    return daily_duties


def tp_journeys(route, turn, tps):
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
    after_departure = tps > (route['departure_time'] - TIME_INT_IS)
    before_return = tps < (route['arrival_time'] + turndelta)
    return ~(after_departure & before_return)


def find_vehicle_spec(specs):
    """Finds the vehicle specifications based on specification IDs"""
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT spec_id, vehicle_model, fuel_type, quoted_range_mile, energy_use,
            battery_size, charge_power_ac, charge_power_dc
            FROM t_vehicle_specification WHERE spec_id IN {specs}"""
        df = pd.read_sql_query(sql_query, cnx, index_col='spec_id')
    except (Exception, psycopg2.Error) as error:
        logger.error("Error fetching vehicle specs")
        raise(error)
    finally:
        cnx.dispose()
    return df


def find_tru_spec(specs):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT tru_id, name, shorepower_summer_kw, shorepower_winter_kw,
            route_power_summer_kw, route_power_winter_kw
            FROM t_tru_specs WHERE tru_id IN {specs}"""
        df = pd.read_sql_query(sql_query, cnx, index_col='tru_id')
    except (Exception, psycopg2.Error) as error:
        logger.error("Error fetching TRU specs")
        raise(error)
    finally:
        cnx.dispose()
    return df


def get_routes(alloc, connection, cur):
    """Get all the routes in a given allocation ID

    Args:
        alloc (int): allocation ID
    """
    idx = alloc['allocation_id']
    routes = cleaner.get_allocated_routes(idx, connection, cur)
    routes = cleaner.get_daily_route_data(
        routes, alloc, connection, cur
        ).sort_index()
    routes['duration_hours'] = (routes['arrival_time']
                                - routes['departure_time']
                                ).dt.total_seconds()/3600
    routes['date'] = routes['departure_time'].dt.date
    routes['start_time'] = (
        routes['departure_time'] - dt.datetime(2022, 1, 1)
        ).dt.total_seconds()/3600 % 24
    routes['end_time'] = (
        routes['arrival_time'] - dt.datetime(2022, 1, 1)
        ).dt.total_seconds()/3600 % 24
    return routes


def get_intershift_periods(routes, grouped, idx):
    """Find how many many HH charging periods are available
    """
    start_dt = grouped.loc[idx, 'departure_time']
    start_tp = (start_dt
                - (start_dt - dt.datetime(2022, 1, 1)) % TIME_INT_IS)
    end_dt = grouped.loc[idx, 'arrival_time']
    end_tp = end_dt + (dt.datetime(2023, 1, 1) - end_dt) % TIME_INT_IS
    tps = np.arange(start=start_tp, step=TIME_INT_IS, stop=end_tp)
    masklist = []
    dutyR = routes[routes['duty_id'] == idx].index
    # Calculate IS shifts
    for r in dutyR:
        masklist.append(tp_journeys(routes.loc[r], TURN, tps))
    n = len(masklist)
    tps = np.sum(np.vstack(masklist).sum(axis=0) == n)
    return tps


def allocation_grouping(alloc, drive, max_rate_ac, max_rate_dc,
                        connection, cur, charger_efficiency=0.9):
    """Gets the daily vehicle duty energy requirements for a given allocation ID

    The feasibility of a given vehicle duty is based on the available time to
    charge between routes, this is called the "intershift" potential

    Args:
        alloc (int): allocation ID
        drive (float): kwh/mile energy use of the EV
        max_rate_ac (float): max AC charge rate of the EV
        max_rate_dc (_type_): max DC charge rate of the EV
    """
    try:
        xmpg = alloc['xmpg']
        # Get all the routes for a given allocation ID
        routes = get_routes(alloc, connection, cur)
        # Group routes into daily duties
        grouped = group_routes(routes)
        charging_rate_ac = max_rate_ac*charger_efficiency
        charging_rate_dc = max_rate_dc*charger_efficiency
        # For each daily duty calculate the number of possible intershift
        # half-hourly charging periods
        for idx in grouped.index:
            tps = get_intershift_periods(routes, grouped, idx)
            grouped.loc[idx, 'TPs'] = tps
        # Calculate real world energy consumption
        kwh_mile = drive / xmpg
        # Calculate how much extra mileage you can get in a vehicle duty
        # based on the AC and DC chargers
        grouped['extra_mileage_ac'] = (grouped['TPs']*TP_FRACT_IS
                                       * charging_rate_ac / kwh_mile)
        grouped['extra_mileage_dc'] = (grouped['TPs']*TP_FRACT_IS
                                       * charging_rate_dc / kwh_mile)
        # Reduce the mileage requirement for a vehicle duty based on the
        # available charging potential
        grouped['reduced_mileage_ac'] = (
            grouped['distance_miles']-grouped['extra_mileage_ac']).clip(
                lower=grouped['ind_mileage'])
        grouped['reduced_mileage_dc'] = (
            grouped['distance_miles']-grouped['extra_mileage_dc']).clip(
                lower=grouped['ind_mileage'])
    except Exception as e:
        raise e
    cols_routes = ['duty_id', 'date', 'distance_miles', 'allocated_vehicle_id']
    return routes[cols_routes], grouped


def calculate_feasibility(grouped, range):
    """Calculate an average feasibility for each vehicle duty

    Args:
        grouped (DataFrame): table of vehicle duties
        range (float): EV range (miles)
    """
    grouped['feasible_nois'] = grouped['distance_miles'] < range
    grouped['feasible_withac'] = ((grouped['distance_miles'] >= range)
                                  & (grouped['reduced_mileage_ac'] < range))
    grouped['feasible_withdc'] = ((grouped['reduced_mileage_ac'] >= range)
                                  & (grouped['reduced_mileage_dc'] < range))
    grouped['unfeasible_withdc'] = (grouped['reduced_mileage_dc'] >= range)
    # ev_possible means that it's possible to do this duty with an EV
    # (even if it takes DC charging)
    grouped['ev_possible'] = ~grouped['unfeasible_withdc']
    return


def upload_ev_routes(routes, electric_drive, diesel_drive, new_allocation):
    routes['energy_required_kwh'] = (
        routes['distance_miles']
        * (routes['allocated_spec_id'].map(electric_drive)))
    routes['diesel_fuel_consumption'] = (
        routes['distance_miles']
        * (routes['allocated_spec_id'].map(diesel_drive)))
    routes['allocation_id'] = new_allocation
    routes['shift'] = 1
    routes['route_cost'] = 0
    dbh.upload_table(routes.reset_index().drop(columns=['distance_miles']),
                     't_route_allocated')
    return


def ev_feasibility_dict(duties, ev_spec, feasibility_threshold=0.94):
    """Decide if each vehicle can be switched by an EV

    This calculates how often the daily duties are feasible, for each EV.
    If this value is above a given threshold, it marks that vehicle
    with the EV spec

    Args:
        duties (_type_): _description_
        ev_spec (_type_): _description_

    Returns:
        _type_: _description_
    """
    ev_feasibility = duties.groupby('allocated_vehicle_id'
                                    )['ev_possible'].mean()
    vehicle_choice_dict = {True: ev_spec,
                           False: duties['allocated_spec_id'].mean()}
    vehicle_spec = (ev_feasibility > feasibility_threshold
                    ).map(vehicle_choice_dict)
    vehicle_spec_dict = vehicle_spec.to_dict()
    return vehicle_spec_dict


def upload_dict_to_db(dict_toupload, connection, cur):
    """Upload road to allocation table"""
    cols = tuple(dict_toupload.keys())
    cols_str = ", ".join(cols)
    vals = tuple([dict_toupload[k] for k in cols])
    sql_query = f"""INSERT INTO t_allocation ({cols_str}) VALUES {vals}"""
    cur.execute(sql_query)
    connection.commit()
    return


def upload_new_allocation(alloc, new_id, routes, ev_vehicle_map,
                          ac_charger, dc_charger, number_dc, feasibility_count,
                          connection, cur):
    """Creates a new entry in the allocation table with the summary of
    the feasibility analysis

    Args:
        alloc (dict): dictionary of allocation inputs
        new_id (int): new allocation ID
        routes (DataFrame): table of routes for this allocation ID
        ev_vehicle_map (dict): Dictionary of specification IDs per vehicle
        ac_charger (int): AC charger power
        dc_charger (int): DC charger power
        number_dc (int): number of DC chargers
        feasibility_count (Series): summary of feasibility based on no
        intershift chargin, ac and dc intershift charging

    Returns:
        int: next available allocation ID
    """
    new_alloc = alloc.copy()
    new_alloc['allocation_id'] = new_id
    new_alloc['original_allocation'] = alloc['allocation_id']
    veh2 = alloc['vehicle1']
    veh1 = routes['allocated_spec_id'].max()
    veh1_ids = [key for key in ev_vehicle_map.keys()
                if ev_vehicle_map[key] == veh1]
    veh2_ids = [key for key in ev_vehicle_map.keys()
                if ev_vehicle_map[key] == veh2]
    new_alloc['start_date'] = str(alloc['start_date'])
    new_alloc['end_date'] = str(alloc['end_date'])
    new_alloc['vehicle1'] = veh1
    new_alloc['vehicle2'] = veh2
    new_alloc['num_r'] = len(routes)
    new_alloc['num_v'] = len(routes['allocated_vehicle_id'].unique())
    new_alloc['num_v_final'] = new_alloc['num_v']
    new_alloc['num_vehicle1'] = len(veh1_ids)
    new_alloc['num_vehicle2'] = len(veh2_ids)
    new_alloc['charger1'] = ac_charger
    new_alloc['charger2'] = dc_charger
    new_alloc['num_charger1'] = new_alloc['num_v'] - number_dc
    new_alloc['num_charger2'] = number_dc
    new_alloc['cap_vehicles'] = False
    new_alloc['allocation_score'] = 0
    new_alloc['overnight_error'] = 0
    if new_alloc['num_vehicle2'] > 0:
        new_alloc['vcategory'] = 'mixed'
    else:
        new_alloc['vcategory'] = 'electric'
    new_alloc['n_duties'] = len(routes['duty_id'].unique())
    new_alloc['n_feas_nois'] = feasibility_count['feasible_nois']
    new_alloc['n_feas_withis'] = (feasibility_count['feasible_withac']
                                  + feasibility_count['feasible_withdc'])
    new_alloc['n_unfeas'] = feasibility_count['unfeasible_withdc']
    new_alloc['n_r_rem'] = 0
    upload_dict_to_db(new_alloc, connection, cur)
    return new_alloc


def read_routes(comment):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT route_id, actual_start_time, actual_end_time,
            number_order, distance_miles, site_id_start, site_id_end,
            vehicle_id FROM t_route_formatted
            WHERE comment = '{comment}'"""
        routes = pd.read_sql_query(sql_query, cnx)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching telematics")
        raise error
    finally:
        cnx.dispose
    # TODO Check datatypes
    return routes


def get_site_name_dict(client):
    """Creates a dictionary of site IDs and site names

    Args:
        client (int): client ID

    Returns:
        dict: site ID: site name
    """
    try:
        connection, cur = dbh.database_connection('test')
        sql_query = f"""SELECT site_id, site_name
            FROM t_sites WHERE client_id={client}"""
        cur.execute(sql_query)
        connection.commit()
        site_data = cur.fetchall()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching site data")
        raise error
    finally:
        cur.close()
        connection.close()
    site_name_dict = {site[0]: site[1]
                      for site in site_data}
    return site_name_dict


def right_start_site(start_id, site):
    return start_id in site


def read_telematics(runs, con):
    COLS = ['departure_time', 'departure_location', 'arrival_time',
            'arrival_location', 'distance_miles', 'driving_time',
            'vehicle_id', 'journey_node_id', 'route_id', 'run', 'client_id',
            'departure_site_id', 'arrival_site_id', 'site_id']
    try:
        cols_telematics = ", ".join(COLS)
        sql_query = f"""SELECT {cols_telematics} FROM t_telematics
            WHERE run IN {runs}"""
        telematics = pd.read_sql_query(sql_query, con)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching telematics")
        raise error
    # TODO Check datatypes
    # telematics['distance_miles'] = telematics['distance_miles'].clip(lower=0)
    return telematics


def find_runs(runs):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT * FROM t_run_allocation
            WHERE run_id IN {runs}"""
        run_table = pd.read_sql_query(sql_query, cnx)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error fetching run data")
        raise(error)
    finally:
        cnx.dispose()
    return run_table


def load_charging_profile(scen):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT * FROM t_charge_demand
            WHERE scenario_id={scen}"""
        demand = pd.read_sql_query(sql_query, cnx)
    except (Exception, psycopg2.Error) as error:
        logger.error("Error getting charge profiles")
        raise(error)
    finally:
        cnx.dispose()
    return demand


def allocation_summary(allocation, drive, range_wltp):
    try:
        cnx = dbh.create_alch_engine()
        alloc = find_allocation(allocation, cnx)
        routes = cleaner.get_allocated_routes(allocation)
        routes = cleaner.get_daily_route_data(routes, alloc).sort_index()
        routes['category'] = 'x'
        grouped = mixed.group_routes(routes)
        charging_rate = 50*0.9
        for idx in grouped.index:
            masklist = []
            dutyR = routes[
                (routes['date'] == idx[0])
                & (routes['allocated_vehicle_id'] == idx[1])].index
            # Calculate IS shifts
            for r in dutyR:
                masklist.append(mixed.tp_journeys(routes.loc[r], TURN))
            masklist.append(
                np.array(POTENTIAL_TPS_IS)
                > (grouped.loc[idx, 'departure_time']
                   - grouped.loc[idx, 'route_date']))
            masklist.append(
                np.array(POTENTIAL_TPS_IS)
                < (grouped.loc[idx, 'arrival_time']
                   - grouped.loc[idx, 'route_date']))
            n = len(masklist)
            tps = np.sum(np.vstack(masklist).sum(axis=0) == n)
            grouped.loc[idx, 'TPs'] = tps
        veh = alloc['vehicle2']
        kwh_mile = drive[veh] / XMPG  # real-world
        grouped['extra_mileage'] = (grouped['TPs']*TP_FRACT_IS*charging_rate
                                    / kwh_mile)
        grouped['reduced_mileage'] = (
            grouped['distance_miles'] - grouped['extra_mileage']).clip(
                lower=grouped['IndMileage']*XMPG)
        feasible = (grouped['distance_miles'] < range_wltp[veh] * XMPG).sum()
        unfeasible_nois = (
            (grouped['distance_miles'] >= range_wltp[veh] * XMPG)
            & (grouped['reduced_mileage'] < range_wltp[veh] * XMPG)).sum()
        unfeasible_withis = (grouped['reduced_mileage']
                             >= range_wltp[veh] * XMPG).sum()
        n_duties = len(grouped)
        n_routes = len(routes)
        site = alloc['site_id']
        n_veh = routes['allocated_vehicle_id'].max()
    except Exception as e:
        raise e
    finally:
        cnx.dispose()
    return [feasible, unfeasible_nois, unfeasible_withis, n_duties,
            n_routes, veh, site, n_veh]


def allocation_summary2(allocation, range_real, connection, cur):
    try:
        cnx = dbh.create_alch_engine()
        alloc = find_allocation(allocation)
        routes = cleaner.get_allocated_routes(allocation, connection, cur)
        routes = cleaner.get_daily_route_data(
            routes, alloc, connection, cur
            ).sort_index()
        routes['category'] = 'x'
        grouped = mixed.group_routes(routes)
        feasible = (grouped['distance_miles'] < range_real).sum()
        unfeasible_nois = (grouped['distance_miles'] >= range_real).sum()
        n_duties = len(grouped)
        n_routes = len(routes)
        n_veh = len(routes['allocated_vehicle_id'].unique())
    except Exception as e:
        raise e
    finally:
        cnx.dispose()
    return [feasible, unfeasible_nois, n_duties, n_routes, n_veh]


def original_routes(idx):
    try:
        connection, cur = dbh.database_connection('test')
        sql_query = f"""SELECT num_r, num_v_final FROM t_allocation WHERE allocation_id={idx}
                ORDER BY allocation_id DESC LIMIT 1"""
        cur.execute(sql_query)
        connection.commit()
        num = cur.fetchall()[0]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching allocation table")
        raise error
    finally:
        cur.close()
        connection.close()
    return num


def find_scenario(allocation):
    scenario = 0
    try:
        connection, cur = dbh.database_connection('test')
        sql_query = f"""SELECT scenario_id FROM t_charging_scenarios
            WHERE allocation_id={allocation}
            ORDER BY scenario_id LIMIT 1"""
        cur.execute(sql_query)
        connection.commit()
        fetch = cur.fetchall()
        if len(fetch) > 0:
            scenario = fetch[0][0]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error finding scenario_id")
        raise error
    finally:
        cur.close()
        connection.close()
    return scenario


def find_all_scenarios(allocations):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT scenario_id, allocation_id, smart_charging,
            output_kwh FROM t_charging_scenarios
            WHERE allocation_id IN {tuple(allocations)}
            ORDER BY allocation_id"""
        scenarios = pd.read_sql_query(sql_query, con=cnx,
                                      index_col='scenario_id')
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching scenario table")
        raise error
    finally:
        cnx.dispose()
    return scenarios


def good_scenario_check(df, a, scenarios):
    bau = df.loc[a, 'bau_scenario']
    bau_good = ((scenarios.loc[bau, 'allocation_id'] == a)
                & (scenarios.loc[bau, 'smart_charging'] is False)
                & (scenarios.loc[bau, 'output_kwh'] > 0))
    opt = df.loc[a, 'sc_scenario']
    opt_good = ((scenarios.loc[opt, 'allocation_id'] == a)
                & (scenarios[(scenarios['allocation_id'] == a)
                             * (scenarios['smart_charging'] is True)
                             ].index.min() == opt))
    mins = df.loc[a, 'min_asc_scenario']
    mins_good = ((scenarios.loc[mins, 'allocation_id'] == a)
                 & (scenarios.loc[mins, 'smart_charging'] is True)
                 & (mins >= opt))
    return bau_good & opt_good & mins_good


def find_max_demand(scenario):
    try:
        cnx = dbh.create_alch_engine()
        sql_query = f"""SELECT datetime, power_demand_kw FROM t_charge_demand
            WHERE scenario_id={scenario}"""
        demand = pd.read_sql_query(sql_query, con=cnx
                                   ).groupby('datetime').sum()
        max_demand = demand['power_demand_kw'].max()
        demand['time'] = demand.index.time
        max_demand_idx = demand['power_demand_kw'].idxmax()
        max_demand_time = demand.loc[max_demand_idx, 'time']
        mask_high_demand = demand['power_demand_kw'] > max_demand*0.95
        mode_time = demand[mask_high_demand]['time'].mode().loc[0]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error fetching max demand")
        raise error
    finally:
        cnx.dispose()
    return max_demand, max_demand_time, mode_time


# OUTPUTS #


def plot_profile(scenario, date):
    try:
        cnx = dbh.create_alch_engine()
        profiles_bau = load_charging_profile(scenario, cnx)
        charge_profiles = profiles_bau.groupby('datetime')['power_demand_kw'
                                                           ].sum()
        charge_profiles = charge_profiles.sort_index().rename('bau')
        logger_dates = charge_profiles.sort_values(ascending=False).index[:3]
        logger.debug(f"dates: {logger_dates.values}")
        # EV charging
        fig, ax = plt.subplots(
            1, figsize=(6, 6), gridspec_kw={'hspace': 0.5})

        ax.set_title(
            f"Scenario {scenario}\nEV Charging Profiles",
            color=FPS_COLOURS[0], fontweight='bold')
        ax.plot(
            charge_profiles.index,
            charge_profiles,
            color=FPS_COLOURS[0])
        # ax.legend(frameon=False, bbox_to_anchor=(1, 0.8))
        ax.set_ylabel('Power Demand (kVA)', color=FPS_COLOURS[0])
        ax.set_xlabel('Time', color=FPS_COLOURS[0])
        ax.set_xlim(left=date, right=date+dt.timedelta(days=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.savefig(
            f"sample/argos3/demand{scenario}.png",
            bbox_inches="tight", dpi=300)
    except Exception as e:
        logger.error(e)
    finally:
        cnx.dispose()
    return


def plot_multi_profiles(profiles, start, labels, name, folder):
    try:
        # EV charging
        fig, ax = plt.subplots(
            1, figsize=(6, 6), gridspec_kw={'hspace': 0.5})

        ax.set_title(
            f"{name}\nEV Charging Profiles",
            color=FPS_COLOURS[0], fontweight='bold')
        for i in range(len(profiles)):
            ax.plot(
                profiles[i].index,
                profiles[i],
                label=labels[i],
                color=FPS_COLOURS[i])
        # ax.legend(frameon=False, bbox_to_anchor=(1, 0.8))
        ax.set_ylabel('Power Demand (kVA)', color=FPS_COLOURS[0])
        ax.set_xlabel('Time', color=FPS_COLOURS[0])
        ax.set_xlim(left=start, right=start+dt.timedelta(days=1))
        ax.legend(frameon=False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.savefig(
            f"sample/{folder}/demand_{name}.png",
            bbox_inches="tight", dpi=300)
    except Exception as e:
        logger.error(e)
    return


def plot_grouped_histo(df, colname, groups, groupcol, groupdict, site_name='',
                       upperclip=None, lowerclip=None, bins=10, folder="-",
                       suff='', vline_dict=None, title_text=None,
                       plot_mean=True, ylim=None):
    fig, ax = plt.subplots(
        1, figsize=(8, 4), gridspec_kw={'hspace': 0.8})
    if title_text is None:
        title_text = site_name
    ax.set_title(
        f'{title_text} \n {colname} distribution',
        color=FPS_COLOURS[0], fontweight='bold', pad=20)
    x = []
    labels = []
    for group in groups:
        mask_group = df[groupcol] == group
        x.append(df.loc[mask_group, colname].clip(upper=upperclip,
                                                  lower=lowerclip))
        labels.append(groupdict[group])
    r = ax.hist(
        x,
        color=FPS_COLOURS[:len(x)], label=labels,
        bins=bins, stacked=True)

    ax.set_ylabel('# of routes', color=FPS_COLOURS[0])
    ax.set_xlabel(f'{colname}', color=FPS_COLOURS[0])
    ax.text(x=r[1][-1]*1.4, y=r[0].max()/2, s=(
        f"{len(df)} entries\n"
        f"Mean: {np.round(df[colname].mean(), 1)}\n"
        f"Max: {np.round(df[colname].max(), 1)}\n"
        f"Median: {np.round(df[colname].median(), 1)}\n"
        f"{np.round((df[colname] > upperclip).mean()*100, 1)}% "
        f"over threshold {upperclip}\n"
        f"{np.round((df[colname] < lowerclip).mean()*100, 1)}% "
        f"under threshold {lowerclip}"
        ))
    if vline_dict:
        for i, key in enumerate(vline_dict.keys()):
            ax.axvline(x=vline_dict[key], label=key,
                       color=FPS_COLOURS[(i+len(groups)) % len(FPS_COLOURS)])
        ax.legend(frameon=False, bbox_to_anchor=(1, 0), loc='lower left')
    if plot_mean:
        ax.axvline(x=df[colname].mean(),
                   color='black', ls='--')
    if ylim:
        ax.set_ylim(bottom=ylim[0], top=ylim[1])
    fig.savefig(
        f"sample/{folder}/{site_name}_histo_{colname}{suff}.png",
        bbox_inches="tight", dpi=300)
    return


def plot_stacked_bar(df, site_name='', x_axis='', y_axis='', folder="-",
                     suff='', title_text=None):
    fig, ax = plt.subplots(
        1, figsize=(8, 4), gridspec_kw={'hspace': 0.5})
    if title_text is None:
        title_text = site_name
    ax.set_title(
        title_text,
        color=FPS_COLOURS[0], fontweight='bold')
    ax = df.plot.bar(ax=ax, stacked=True)
    ax.set_ylabel(y_axis, color=FPS_COLOURS[0])
    ax.set_xlabel(x_axis, color=FPS_COLOURS[0])
    ax.set_xticks(ax.get_xticks(), ax.get_xticklabels(),
                  rotation=45, ha='right')
    ax.legend(frameon=False, bbox_to_anchor=(1, 0), loc='lower left')
    fig.savefig(
        f"sample/{folder}/{site_name}_stacked_{x_axis}{suff}.png",
        bbox_inches="tight", dpi=300)
    return


def pie_chart(sizes, labels, site_name, folder="-", suff='',
              title_text=None, autopct=None, labeldistance=1.1):
    fig, ax = plt.subplots(
        1, figsize=(8, 3), gridspec_kw={'hspace': 0.5})
    if title_text is None:
        title_text = site_name
    ax.set_title(
        f'{title_text}',
        color=FPS_COLOURS[0], fontweight='bold', pad=20)
    ax.pie(sizes, labels=labels, startangle=90,
           autopct=autopct,
           colors=FPS_COLOURS[:len(sizes)], labeldistance=labeldistance)
    ax.axis('equal')
    ax.legend(frameon=False)
    fig.savefig(
        f"sample/{folder}/{site_name}_pie{suff}.png",
        bbox_inches="tight", dpi=300)
    return


def histo_variable(df, colname, site_name, upperclip=None,
                   lowerclip=None, bins=10, folder="-",
                   suff='', vline_dict=None, title_text=None,
                   plot_mean=True, cumdist=False):
    fig, ax = plt.subplots(
        1, figsize=(8, 3), gridspec_kw={'hspace': 0.5})
    if title_text is None:
        title_text = site_name
    ax.set_title(
        f'{title_text} \n {colname} distribution',
        color=FPS_COLOURS[0], fontweight='bold')
    r = ax.hist(
        df[colname].clip(upper=upperclip, lower=lowerclip),
        color=[FPS_COLOURS[0]],
        bins=bins, cumulative=cumdist, density=cumdist)

    ax.set_ylabel('# of routes', color=FPS_COLOURS[0])
    ax.set_xlabel(f'{colname}', color=FPS_COLOURS[0])
    ax.text(x=r[1][-1]*1.1, y=r[0].max()/2, s=(
        f"{len(df)} entries\n"
        f"Mean: {np.round(df[colname].mean(), 1)}\n"
        f"Max: {np.round(df[colname].max(), 1)}\n"
        f"Median: {np.round(df[colname].median(), 1)}\n"
        f"{np.round((df[colname] > upperclip).mean()*100, 1)}% "
        f"over threshold {upperclip}\n"
        f"{np.round((df[colname] < lowerclip).mean()*100, 1)}% "
        f"under threshold {lowerclip}"
        ))
    if vline_dict:
        for i, key in enumerate(vline_dict.keys()):
            ax.axvline(x=vline_dict[key], label=key,
                       color=FPS_COLOURS[(i+1) % len(FPS_COLOURS)])
        ax.legend(frameon=False, bbox_to_anchor=(1, 0), loc='lower left')
    if plot_mean:
        ax.axvline(x=df[colname].mean(),
                   color='black', ls='--',
                   label=f"Mean: {np.round(df[colname].mean(), 1)}")
        ax.legend(frameon=False, bbox_to_anchor=(1, 0), loc='lower left')
    fig.savefig(
        f"sample/{folder}/{site_name}_histo_{colname}{suff}.png",
        bbox_inches="tight", dpi=300)
    return


def bar_plot_vehicle_sites(routes, site_dict, site_veh_count):
    grouped = routes.groupby(['site_id_start', 'vehicle_id']).count()[[
        'route_id', 'distance_miles']]
    grouped = grouped.groupby('site_id_start').count()
    grouped['site_name'] = grouped.index.map(site_dict).fillna('other')
    grouped = grouped.merge(site_veh_count, left_index=True, right_index=True,
                            how='left')
    grouped = grouped.reset_index()
    # print(grouped.head())
    fig, ax = plt.subplots(
        1, figsize=(8, 3), gridspec_kw={'hspace': 0.5})
    ax.set_title(
        'Vehicle locations',
        color=FPS_COLOURS[0], fontweight='bold')
    ax.bar(
        x=grouped.index-0.2,
        height=grouped['route_id'], width=0.5,
        color=[FPS_COLOURS[0]], label='According to route starts')
    ax.bar(
        x=grouped.index,
        height=grouped['vehicle_id'], width=0.5,
        color=[FPS_COLOURS[1]], label='According to microlise groups')

    ax.legend(frameon=False, bbox_to_anchor=(1, 0.8))
    ax.set_ylabel('# of vehicles', color=FPS_COLOURS[0])
    ax.set_xlabel('Site', color=FPS_COLOURS[0])
    ax.xaxis.set_major_locator(
        matplotlib.ticker.FixedLocator(np.arange(len(grouped))))
    ax.set_xticklabels(grouped['site_name'], rotation=45, ha='right')
    n_veh = len(routes['vehicle_id'].unique())
    ax.text(x=len(grouped)+2, y=grouped['route_id'].max()/2,
            s=f'{n_veh} vehicles in total')
    fig.savefig(
        "sample/hgv2/where_vehicles_work.png",
        bbox_inches="tight", dpi=300)
    return


def violin_plot(distribution_array, variable, site_name, labels=None,
                suff="", folder="-",):
    fig, ax = plt.subplots(
        1, figsize=(6, 3), gridspec_kw={'hspace': 0.5})
    ax.set_title(
        f'How many {variable} return to site?',
        color=FPS_COLOURS[0], fontweight='bold')
    N = len(labels)
    r = ax.violinplot(distribution_array)
    ax.xaxis.set_major_locator(
        matplotlib.ticker.FixedLocator(np.arange(1, N+1)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_ylabel(f'% of {variable} returning to site', color=FPS_COLOURS[0])
    ax.set_xlabel("Type of vehicle", color=FPS_COLOURS[0])

    fig.savefig(
        f"sample/{folder}/{site_name}_violin{suff}.png",
        bbox_inches="tight", dpi=300)
    return r


def bar_plot_site_starts(routes, site_dict, site=0):
    grouped = routes.groupby(
        ['site_id_start', 'same_return']
        )['route_id'].count().unstack(fill_value=0)
    grouped['site_name'] = grouped.index.map(site_dict).fillna('other')
    grouped['n_routes'] = grouped[True] + grouped[False]
    grouped = grouped.sort_values(by='n_routes', ascending=False).reset_index()
    grouped = grouped[grouped['n_routes'] > 5]

    fig, ax = plt.subplots(
        1, figsize=(8, 3), gridspec_kw={'hspace': 0.5})
    ax.set_title(
        f'Vehicles asigned to {site_dict[site]} \n Where do routes start?',
        color=FPS_COLOURS[0], fontweight='bold')
    ax.bar(
        x=grouped.index,
        height=grouped[True],
        color=[FPS_COLOURS[0]], label='Same return site')
    ax.bar(
        x=grouped.index,
        height=grouped[False], bottom=grouped[True],
        color=[FPS_COLOURS[1]], label='Different return site')

    ax.legend(frameon=False, bbox_to_anchor=(1, 0.8))
    ax.set_ylabel('# of routes', color=FPS_COLOURS[0])
    ax.set_xlabel('Site', color=FPS_COLOURS[0])
    ax.xaxis.set_major_locator(
        matplotlib.ticker.FixedLocator(np.arange(len(grouped))))
    ax.set_xticklabels(grouped['site_name'], rotation=45, ha='right')
    # ax.text(x=len(grouped)+2, y=grouped['n_routes'].max()/2,
    #   s=f'{len(routes)} Routes')
    n_same_start = sum(routes['start_right_id'])
    right_start_pc = 100*n_same_start/len(routes)
    same_site_pc = 100*routes['same_return'].mean()
    ax.text(x=len(grouped)+2, y=grouped['n_routes'].max()/2, s=(
        f"{len(routes)} Routes\n"
        f"{np.round(right_start_pc, 1)}% start on the right site\n"
        f"{np.round(same_site_pc, 1)}% return to same site"
        ))
    fig.savefig(
        f"sample/hgv2/{site_dict[site]}_site_starts.png",
        bbox_inches="tight", dpi=300)
    return


def bar_plot_site_ends(routes, site_dict, site, suff='', ):
    grouped = routes.groupby(
        ['site_id_end', 'start_right_id']
        )['route_id'].count().unstack(fill_value=0)
    grouped['site_name'] = grouped.index.map(site_dict).fillna('other')
    for c in [True, False]:
        if c not in grouped.columns:
            grouped[c] = 0
    grouped['n_routes'] = grouped[True] + grouped[False]
    grouped = grouped.sort_values(by='n_routes', ascending=False).reset_index()
    fig, ax = plt.subplots(
        1, figsize=(8, 3), gridspec_kw={'hspace': 0.5})
    ax.set_title(
        f'Routes starting from {site_dict[site]} \n Where do routes end?',
        color=FPS_COLOURS[0], fontweight='bold')
    ax.bar(
        x=grouped.index,
        height=grouped[True],
        color=[FPS_COLOURS[0]], label=f'Originally from {site_dict[site]}')
    ax.bar(
        x=grouped.index,
        height=grouped[False], bottom=grouped[True],
        color=[FPS_COLOURS[1]], label=f'Originally NOT from {site_dict[site]}')

    ax.legend(frameon=False, bbox_to_anchor=(1, 0.8))
    ax.set_ylabel('# of routes', color=FPS_COLOURS[0])
    ax.set_xlabel('Site', color=FPS_COLOURS[0])
    ax.xaxis.set_major_locator(
        matplotlib.ticker.FixedLocator(np.arange(len(grouped))))
    ax.set_xticklabels(grouped['site_name'], rotation=45, ha='right')
    right_start_pc = 100*routes['start_right_id'].mean()
    same_site_pc = 100*routes['same_return'].mean()
    ax.text(x=len(grouped)+2, y=grouped['n_routes'].max()/2, s=(
        f"{len(routes)} Routes\n"
        f"{np.round(right_start_pc, 1)}% originally from site\n"
        f"{np.round(same_site_pc, 1)}% return to same site"
        ))
    fig.savefig(
        f"sample/hgv2/{site_dict[site]}_site_ends{suff}.png",
        bbox_inches="tight", dpi=300)
    return
