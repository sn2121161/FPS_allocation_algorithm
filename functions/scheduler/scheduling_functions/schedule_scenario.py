import numpy as np
import pandas as pd
import os
import psycopg2
# import sqlalchemy
import datetime as dt
# import json
# import sys
import pipeline_plan_functions.utils.pipe_db_handler as dbh
import pipeline_plan_functions.utils.data_handler as dh
import pipeline_plan_functions.utils.data_types as dth
from python_utils.utils.logger import logger
from scheduling_functions import optimisation as opt
# import optimisation as opt
from scheduling_functions import cleanup
import multiprocessing

logger.setLevel(os.getenv('log_level', "DEBUG"))

TIME_FRACT = 0.5
CHARGER_EFF = 0.9  # FIXME put this in the database
BATTERY_FACTOR = 0
ASC_XUSE = 0.9
DEFAULT_EPRICE = 0.12
THREAD_WAIT = 300


def get_scheduling_inputs(scenario, connection, cur, cnx):
    """Get all the inputs associated to a scenario ID"""
    try:
        sql_query = (f"""SELECT *
            FROM t_charging_scenarios WHERE scenario_id={scenario}""")
        cur.execute(sql_query)
        connection.commit()
        desc = cur.description
        values = cur.fetchall()[0]
        column_names = [col[0] for col in desc]
        inputs = dict(zip(column_names, values))
        inputs_run = dh.get_inputs('t_run_charging', inputs['run_id'],
                                   connection, cur)
        for c in inputs_run.keys():
            inputs[c] = inputs_run[c]
        # Update t_charging_scenarios status to "p" for "in progress"
        sql_query = f"""UPDATE t_charging_scenarios SET schedule_status='p'
            WHERE scenario_id={scenario}"""
        cur.execute(sql_query)
        connection.commit()
        sql_query = f"""SELECT site_id, route_table FROM t_allocation
            WHERE allocation_id={inputs['allocation_id']}"""
        inputs_alloc = pd.read_sql_query(sql_query, cnx).loc[0].to_dict()
        for c in inputs_alloc.keys():
            inputs[c] = inputs_alloc[c]
    except (Exception, psycopg2.Error) as error:
        logger.error("Couldn't get all input parameters")
        raise error
    return inputs


def get_route_data(routes, params, cnx):
    """Fetch the original route data required and merges it all together"""
    orig_routes = get_routes_fromid(routes.index, params['route_table'], cnx)
    route_cols = ['departure_time', 'arrival_time']
    routes = routes.merge(orig_routes[route_cols],
                          left_index=True,
                          right_index=True)
    routes['end_time'] = routes['arrival_time'] + dt.timedelta(
        minutes=params['min_to_connect'])
    routes.drop(columns=[
        'category', 'diesel_fuel_consumption', 'allocation_id', 'shift',
        'route_cost', 'arrival_time'
    ],
                inplace=True)
    # Select only routes that have positive energy requirements
    routes = routes[routes['energy_required_kwh'] > 0]
    if len(routes) == 0:
        logger.info("No EV routes to schedule")
    return routes


def list_dates(dates, max_n):
    """Creates a list of dates to optimise based on the route dates
    """
    start_date = dates.min().to_pydatetime()
    end_date = dates.max().to_pydatetime()
    N = int((end_date - start_date).total_seconds() / (24 * 3600) + 1)
    # Limits the number of dates based on the input num_days
    N = min(N, max_n)
    date_array = (np.full(N, start_date) + np.arange(N) * dt.timedelta(days=1))
    return date_array


def create_time_periods(dates, params, delta_min=30):
    """Creates half-hourly time intervals covering the whole optimisation
    period

    """
    start_hours = params['day_start_hours']
    profile_start = dates[0] + dt.timedelta(hours=start_hours)
    profile_end = dates[-1] + dt.timedelta(hours=(start_hours + 24))
    nperiods = int(
        (profile_end - profile_start).total_seconds() / (delta_min * 60))
    times = (np.full(nperiods, profile_start) +
             np.arange(nperiods) * dt.timedelta(minutes=delta_min))
    return times


def availability_matrix(vehicles, routes, times):
    """Creates a matrix of vehicle availability and energy use

    The availability matrix contains rows for each time period and
    columns for each vehicle. The value is 1 if the vehicle is available at
    that time, and 0 otherwise.
    The ev use matrix has the same structure but has the value of the energy
    consumption (in kWh) in the time period when the vehicle arrives back at
    the site after a route.

    Args:
        vehicles (array): vehicle IDs
        routes (DataFrame): table of route data
        times (array): time intervals
    """
    T = len(times)
    N = len(vehicles)
    availability = np.ones((T, N))
    evuse = np.zeros((T, N))
    time_int = dt.timedelta(hours=TIME_FRACT)

    for idx in routes.index:
        mask = ((times > routes.loc[idx, 'departure_time'] - time_int / 2)
                & (times < routes.loc[idx, 'end_time'] - time_int / 2))
        vehicle = vehicles.index(routes.loc[idx, 'allocated_vehicle_id'])
        # Assign 0 to availability when vehicle is out
        availability[mask, vehicle] = 0
        # Assign energy used when vehicle returns
        if mask.sum() > 0:
            return_idx = np.where(mask)[0][-1]
            evuse[return_idx,
                  vehicle] = -routes.loc[idx, 'energy_required_kwh']
    return availability, evuse


def availability_matrix_depot(vehicles, routes, times):
    """Creates a matrix of vehicle availability and energy use for HGVs

    The availability matrix contains rows for each time period and
    columns for each vehicle. The value is 1 if the vehicle is available at
    that time, and 0 otherwise.
    The ev use matrix has the same structure but has the value of the energy
    consumption (in kWh) in the time period when the vehicle arrives back at
    the site after a route.

    Args:
        vehicles (array): vehicle IDs
        routes (DataFrame): table of route data
        times (array): time intervals
    """
    T = len(times)
    N = len(vehicles)
    availability = np.zeros((T, N))
    evuse = np.zeros((T, N))
    time_int = dt.timedelta(hours=TIME_FRACT / 2)

    for idx in routes.index:
        # Looks at the period where each HGV is available to recharge
        depot_end = (routes.loc[idx, 'end_time'] +
                     dt.timedelta(hours=routes.loc[idx, 'recharge_hours']))
        mask = ((times >= routes.loc[idx, 'end_time'] - time_int)
                & (times <= depot_end - time_int))
        vehicle = vehicles.index(routes.loc[idx, 'allocated_vehicle_id'])
        # Assign 1 to availability when vehicle is at depot
        availability[mask, vehicle] = 1
        # Assign energy used when vehicle returns
        if mask.sum() > 0:
            return_idx = np.where(mask)[0][0] - 1
            evuse[return_idx,
                  vehicle] = -routes.loc[idx, 'energy_required_kwh']
    return availability, evuse


def vehicle_matrices(vehicles, routes, times):
    """Creates matrices representing the charging requirements

    The charging session matrix contains a row for each charging session. The
    goal is to make sure the same charger is used for a charging session (no
    switching between AC and DC).

    Args:
        vehicles (array): vehicle IDs
        routes (DataFrame): table of route data
        times (array): time intervals

    Raises:
        Exception: _description_

    Returns:
        _type_: _description_
    """
    T = len(times)
    N = len(vehicles)
    if routes['recharge_hours'].sum() == 0:
        availability, evuse = availability_matrix(vehicles, routes, times)
    else:
        availability, evuse = availability_matrix_depot(
            vehicles, routes, times)
    # Return matrix represents when the vehicle returns to site
    return_matrix = (evuse != 0).astype(int)
    return_matrix[0, :] = 1
    # A session matrix is used to group the time intervals of a
    # single charging session
    session_matrix = np.reshape(return_matrix.flatten('F').cumsum(), (T, N),
                                order='F')
    session_matrix = session_matrix * availability
    unique_sessions = np.unique(session_matrix)
    unique_sessions = unique_sessions[unique_sessions > 0]
    sessionM = np.zeros((len(unique_sessions), 3), int)
    # The columns are
    # 0: vehicle index
    # 1: initial time period
    # 2: final time period
    for i, s in enumerate(unique_sessions):
        idxs = np.where(session_matrix == s)
        sessionM[i, 1] = idxs[0][0]
        sessionM[i, 2] = idxs[0][-1] + 1
        sessionM[i, 0] = idxs[1][0]
        different_vehicles = (idxs[1] != idxs[1][0]).any()
        if different_vehicles:
            raise Exception(f"Mistake defining charging sessions. Session {s}"
                            "assigned to multiple vehicles")
    return availability, evuse, sessionM


def get_site_capacity(site, times, sc, asc, cnx):
    """Creates an array of site demand per time period
    """
    if sc:
        # If smart charging
        try:
            # sql_query = f"""
            # SELECT datetime, clean_load  FROM t_site_load
            # WHERE datetime >= '{times[0]}'
            # AND datetime <= '{times[-1]}'
            # AND site_id={site}
            # """
            # table_name = "t_site_load"
            # val_cname = "clean_load"
            table_name = "t_site_load_meter_breakdown"
            val_cname = "main_load_clean"
            sql_query = " ".join([
                f"SELECT datetime, {val_cname}",
                f"FROM {table_name}",
                f"WHERE datetime >= '{times[0]}'",
                f"AND datetime <= '{times[-1]}'",
                f"AND site_id={site}",
            ])
            meter = pd.read_sql_query(sql_query, cnx)
        except (Exception, psycopg2.Error) as error:
            logger.error("Error while fetching site meter data")
            raise error
        meter_df = pd.DataFrame(data=times, columns=['dt'])
        meter_df = meter_df.merge(meter,
                                  left_on='dt',
                                  right_on='datetime',
                                  how='left')
        meter_df[val_cname] = meter_df[val_cname].fillna(0)
        capacity_array = np.clip(asc - meter_df[val_cname].values,
                                 a_min=0,
                                 a_max=None)
    else:
        # If dumb charging (not respecting site capacity)
        capacity_array = np.full(len(times), 10000000)
    return capacity_array


def get_tariff(distributionid,
               times,
               sc,
               cnx,
               tariff="electricity_price_fixed"):
    """Creates a df of electricity pricing for each time period
    """
    elec_array = np.full(len(times), DEFAULT_EPRICE)
    if sc:
        # If smart charging
        try:
            sql_query = f"""SELECT datetime, {tariff} FROM t_electricity_price
                WHERE datetime >= '{times[0]}'
                AND datetime <= '{times[-1]}'
                AND distribution_id={distributionid}
                ORDER BY datetime"""
            electricity = pd.read_sql_query(sql_query, cnx)
        except (Exception, psycopg2.Error) as error:
            logger.error("Error fetching electricity tariff")
            raise error
        elec_df = pd.DataFrame(data=times, columns=['dt'])
        elec_df = elec_df.merge(electricity,
                                left_on='dt',
                                right_on='datetime',
                                how='left')
        elec_df.rename(columns={f"{tariff}": 'price'}, inplace=True)
        elec_df['price'] = elec_df['price'].fillna(method='ffill')
        elec_df['price'] = elec_df['price'].fillna(DEFAULT_EPRICE)
        elec_array = elec_df['price'].values
    return elec_array


def get_site_data(params, connection, cur):
    """ Get relevant data from specific site """
    new_params = params.copy()
    try:
        sql_query = f"""SELECT asc_kw, distribution_id, min_to_connect
            FROM t_sites WHERE site_id={params['site_id']}"""
        cur.execute(sql_query)
        connection.commit()
        desc = cur.description
        values = cur.fetchall()[0]
        for i in range(len(values)):
            new_params[desc[i][0]] = values[i]
        new_params['asc_kw'] = new_params['asc_kw'] * ASC_XUSE
    except Exception as err:
        logger.error(f"Error getting site data {err}")
        raise err
    return new_params


def get_vehicle_specs(spec_ids, connection, cur):
    try:
        if len(spec_ids) > 1:
            sql_query = (
                f"""SELECT spec_id, battery_size, charge_power_ac, charge_power_dc
                FROM t_vehicle_specification
                WHERE spec_id IN {tuple(spec_ids)}""")
        else:
            sql_query = (
                f"""SELECT spec_id, battery_size, charge_power_ac, charge_power_dc
                FROM t_vehicle_specification WHERE spec_id={spec_ids[0]}""")
        cur.execute(sql_query)
        connection.commit()
        values = cur.fetchall()
        spec_dict = {spec[0]: spec[1:] for spec in values}
    except (Exception, psycopg2.Error) as error:
        logger.error("Couldn't get vehicle specs")
        raise error
    return spec_dict


def vehicle_spec_vectors(routes, vehicles, connection, cur):
    """Creates vectors of useful vehicle information, matching the vehicle
    order

    Args:
        routes (DataFrame): table of route data
        vehicles (array): vehicle IDs
    """
    spec_dict = routes.groupby('allocated_vehicle_id').agg(
        {'allocated_spec_id': 'first'})['allocated_spec_id'].to_dict()
    # Get the vehicle specification of each vehicle
    spec_list = np.array([spec_dict[v] for v in vehicles])
    spec_data = get_vehicle_specs(list(set(spec_list)), connection, cur)
    # Each of these vectors represents the battery capacity and charge rate.
    # The order of the values matches the vehicle order in the "vehicle" list
    battery_cap = np.array([spec_data[v][0] for v in spec_list])
    charger_rate_ac = np.array([spec_data[v][1] for v in spec_list])
    charger_rate_dc = np.array([spec_data[v][2] for v in spec_list])
    return battery_cap, charger_rate_ac, charger_rate_dc


def day_matrices(available, evuse, sessionM, charger_efficiency, start, end):
    """Creates the input matrix for a specific day by cropping the full ones
    """
    available_day = available[start:end]
    evuse_day = evuse[start:end]
    shifted_sessions = sessionM[:, 1:3] - start
    mask = ((shifted_sessions >= 0) & (shifted_sessions <= 24)).any(axis=1)
    sessions_day = np.clip(shifted_sessions[mask], a_min=0, a_max=24)
    sessions_day = np.concatenate(
        [sessionM[mask, 0].reshape(-1, 1), sessions_day], axis=1)
    return [available_day, evuse_day, sessions_day, charger_efficiency]


def day_site_vectors(vectors, start, end):
    day_vectors = []
    for v in vectors:
        day_vectors.append(v[start:end])
    return day_vectors


# TODO MOVE these to data handler functions (and in allocation code)


def get_allocated_routes(allocation_id, cnx):
    try:
        sql_query = f"""SELECT *  FROM t_route_allocated
            WHERE allocation_id={allocation_id}"""
        routes = pd.read_sql_query(sql_query, cnx, index_col='route_id')
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching routes/no routes available")
        raise error
    return routes


def get_routes_fromid(routeids, table, cnx):
    route_tuple = dth.list_to_string(routeids)
    try:
        sql_query = f"""SELECT *  FROM {table}
            WHERE route_id IN {route_tuple}"""
        routes = pd.read_sql_query(sql_query, cnx, index_col='route_id')
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching routes/no routes available")
        raise error
    return routes


# Bill adding for QA check
def count_dc_num(evout,params):
    num_charger2 = params['num_charger2']
    # convert to boolean
    dc_charger  = (evout > 11)
    dc_charger_day = dc_charger.sum(axis=1) 
    filtered = filter(lambda a : a > num_charger2, dc_charger_day)
    count = len(list(filtered))
    return count

def soc_change_check(evout,soc_out):
    count = 0
    # filter where evout > 0
    operate_charger = (evout > 0)
    # Find true indexes
    charger_bool = np.where(operate_charger)
    for r in range(charger_bool[0].shape[0]):
        r_index = charger_bool[0][r]
        c_index = charger_bool[1][r]
        # calculate soc difference
        soc_change = soc_out[r_index][c_index] - soc_out[r_index-1][c_index]
        # make comparison
        if evout[r_index][c_index] < soc_change:
            count += 1
    return count
         
         
def main(scenario):
    logger.debug(f"Started schedulling scenario {scenario}")
    try:
        connection, cur = dbh.database_connection('test')
        # Get run input parameters
        cnx = dbh.create_alch_engine()
        params = get_scheduling_inputs(scenario, connection, cur, cnx)
        params = get_site_data(params, connection, cur)
        # params['asc_kw'] = 60  #############
        # Get routes
        routes = get_allocated_routes(params['allocation_id'], cnx)
        routes = get_route_data(routes, params, cnx)
        # # Get list of dates
        dates = list_dates(routes['date'], params['num_days'])
        # # Get time periods (T time periods)
        times = create_time_periods(dates, params)
        ndays = (times[-1] - times[0] + dt.timedelta(hours=TIME_FRACT)).days
        # Get site load
        capacity = get_site_capacity(params['site_id'], times,
                                     params['smart_charging'],
                                     params['asc_kw'], cnx)
        logger.info('asc_kw: %d, asc_margin: %.2f, extraCap: %.2f' % (
            params['asc_kw'],
            params['asc_margin'],
            params['asc_kw'] * params['asc_margin'],
        ))
        # Get electricity price
        electricity = get_tariff(params['distribution_id'], times,
                                 params['smart_charging'], cnx)
        # Get vehicle list (N vehicles)
        vehicles = sorted(routes['allocated_vehicle_id'].unique())
        # Get vehicle availability, energy use matrix (T*N) and session matrix
        available, evuse, session_matrix = vehicle_matrices(
            vehicles, routes, times)
        # Get vehicle spec vectors
        battery_cap, charger_rate_ac, charger_rate_dc = vehicle_spec_vectors(
            routes, vehicles, connection, cur)
        charger_efficiency = np.diag(np.full(int(24 / TIME_FRACT),
                                             CHARGER_EFF))
        # # Make relative charge and required energy vectors
        req_energy_level = -battery_cap  # FIXME
        rel_charge = np.zeros(len(vehicles))
        vehicle_vectors = [
            rel_charge, req_energy_level, battery_cap, vehicles,
            charger_rate_ac, charger_rate_dc
        ]
        site_vectors = [electricity, capacity, times]
        # iterate over each day and filter inputs
        breach_days = []
        magic_days = []
        timeout_days = []
        breaches = 0
        output_kwh = 0
        excess_costs = 0
        # Bill adding
        final_min_soc = 100
        final_max_soc = 0
        # For QA check
        num_charger2_violation = 10
        num_soc_change_violation = 10
        check_dict = {'num_charger2_violation':[],
                      'num_soc_change_violation':[]}
        debug_log = {
            'day': [],
            'output_kwh': [],
            'excess_cost': [],
            'opt_level': [],
            # Bill added
            'min_soc':[]
        }
        day_itr = range(0, ndays)
        # day_itr = [69]
        for day in day_itr:
            # for day in range(500, ndays):
            start = int(day * 24 / TIME_FRACT)
            end = int((day + 1) * 24 / TIME_FRACT)
            logger.info('day %d: start %d - end %d' % (day, start, end))
            matrices = day_matrices(available, evuse, session_matrix,
                                    charger_efficiency, start, end)
            day_vectors = day_site_vectors(site_vectors, start, end)
            # run linear optimiser for each day
            final_soc_arr = multiprocessing.Array('d', np.zeros(len(vehicles)))
            opt_level = multiprocessing.Value('i', -1)
            ev_out_arr = multiprocessing.Array(
                'd', range(len(vehicles) * int(24 / TIME_FRACT)))
            # Bill added
            final_soc_arr_h = multiprocessing.Array(
                'd', range(len(vehicles) * int(24 / TIME_FRACT)))
            # Bill editing final_soc_arr_h in process 
            p = multiprocessing.Process(
                target=opt.linear_optimiser_V10,
                args=(matrices, day_vectors, vehicle_vectors, params,
                      final_soc_arr, opt_level, ev_out_arr,final_soc_arr_h))
            p.start()
            # Wait for 10 seconds or until process finishes
            p.join(THREAD_WAIT)
            # If thread is still active
            if p.is_alive():
                print("running... let's kill it...")
                # Terminate - may not work if process is stuck for good
                p.terminate()
                p.join()
            evout = np.array(ev_out_arr[:]).reshape(int(24 / TIME_FRACT),
                                                    len(vehicles))
            # Bill adding
            soc_out = np.array(final_soc_arr_h[:]).reshape(int(24 / TIME_FRACT),
                                                    len(vehicles))
            min_soc = soc_out.min()
            max_soc = soc_out.max()
            final_soc = np.array(final_soc_arr[:])
            if opt_level.value == 1:
                # there was a site capacity breach
                breach_days.append(day)
                logger.warning('Breach!!! day: %d' % day)
            elif opt_level.value == 2:
                # The optimisation was unfeasible
                magic_days.append(day)
                logger.warning('Magic!!! day: %d' % day)
            elif opt_level.value == -1:
                # The optimisation timed out
                opt_level.value = 2
                evout = opt.magic_charging(matrices, vehicle_vectors)
                timeout_days.append(day)
                logger.warning('Timeout!!! day: %d' % day)
            # Export each day
            # Bill adding one parameter
            cleanup.export_charge_schedule(evout, soc_out, params, vehicles,
                                           times[start:end], cnx)
            breaches += cleanup.calculate_breaches(evout, day_vectors[1])
            output_kwh += evout.sum()
            excess_cost = cleanup.excess_capacity_cost(
                evout, day_vectors[1], params['distribution_id'], connection,
                cur)
            # logger.info('day %d(%s-%s): excess cost: %d, output_kwh: %d' %
            #             (day, times[start], times[end], excess_cost, output_kwh))
            excess_costs += excess_cost
            debug_log['day'].append(day)
            debug_log['output_kwh'].append(output_kwh)
            debug_log['excess_cost'].append(excess_cost)
            debug_log['opt_level'].append(opt_level.value)
            # Bill added
            final_min_soc = min(final_min_soc,min_soc).round(2)
            final_max_soc = max(final_max_soc,max_soc).round(2)
            num_charger2_violation = count_dc_num(evout, params)
            num_soc_change_violation = soc_change_check(evout,soc_out)
            check_dict['num_charger2_violation'].append(num_charger2_violation)
            check_dict['num_soc_change_violation'].append(num_soc_change_violation)
            # update relative energy vector
            vehicle_vectors[0] = final_soc
        n_breach_days = len(breach_days)
        n_magic_days = len(magic_days)
        n_timeout = len(timeout_days)
        cleanup.update_scenarios(breaches, n_breach_days, n_magic_days,
                                 n_timeout, output_kwh, excess_costs, scenario, final_min_soc, final_max_soc,
                                 connection, cur)
        # Bill adding QA check
        df = pd.DataFrame.from_dict(check_dict)
        df.to_csv('QA_check.csv', index=True)

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