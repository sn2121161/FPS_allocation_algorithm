import pandas as pd
import datetime as dt
import logging
import os
import psycopg2
import sqlalchemy
import numpy as np
import numpy_financial as npf

successful_uploads = []
failed_uploads = []


run_id = 215 # USER INPUT: SET A DESIRED RUN ID HERE
client_id = 2 # USER INPUT: SET CLIENT ID HERE
site_ids = [309] # USER INPUT: SET SITE IDS HERE

# database related, maybe can consider store in a seperate file in the future
def database_connection():
    '''Open connections to FPS databse for read and write operations
    Args:
        None
    Returns:
        connection (psycopg2.extensions.connection): connection to FPS database
        cnx (sqlalchemy.engine.base.Engine): engine to interact with FPS database'''

    # Get database credentials from azure key vault
    db_user = os.getenv('pipe_db_user', '')
    db_pswd = os.getenv('pipe_db_pswd', '')
    db_name = os.getenv('pipe_db_name', '')
    db_host = os.getenv('pipe_db_host', '')
    db_port = os.getenv('pipe_db_port', '')
    ssl_mode = os.getenv('pipe_ssl_mode', 'require')
    # connect to PostgreSQL for update
    # print('connect to PostgreSQL for update')
    try:
        connection = psycopg2.connect(user=db_user,
                                      password=db_pswd,
                                      host=db_host,
                                      port=db_port,
                                      database=db_name,
                                      sslmode=ssl_mode)
        # print('successfully generated connection')
    except psycopg2.OperationalError as err:
        print(str(err))
        raise err
    except Exception as err:
        print(str(err))
        raise err

    # connect to PostgreSQL for pd to sql append
    # print('connect to PostgreSQL for Pd to sql append')
    try:
        db_conn_str = sqlalchemy.engine.URL.create(
            drivername='postgresql+psycopg2',
            username=db_user,
            password=db_pswd,
            database=db_name,
            host=db_host,
            port=db_port,
            query={'sslmode': 'require'},
            )
        cnx = sqlalchemy.create_engine(db_conn_str)
        # print('successfully generated engine')
    except sqlalchemy.exc.SQLAlchemyError as err:
        print(str(err))
        raise err
    except Exception as err:
        print(str(err))
        raise err

    return(connection, cnx)


def read_input_data(table, key_nam, key_val):
    '''Read rows from a specified tabled based on a specified column-value'''
    # establish FPS database connection
    if type(key_val) == list:
        key_val = tuple(key_val)
    if type(key_val) == tuple:
        query_str = ('SELECT * FROM ' + table
                + ' WHERE ' + key_nam
                + ' IN %(key_val)s')
    else:
        query_str = ('SELECT * FROM ' + table
                    + ' WHERE ' + key_nam
                    + ' = %(key_val)s')
    params_val = {'key_val': key_val}
    # establish FPS database connection
    try:
        connection, cnx = database_connection()
        print('FPS db connection successful')
        try:
            data = pd.read_sql(query_str,
                                         connection, params=params_val)
            print('data read successful')
        except sqlalchemy.exc.OperationalError as err:
            print('data read unsuccessful')
            raise err
        except ValueError as err:
            print('data read unsuccessful')
            raise err
        finally:
            # close the db connection
            connection.close()
            cnx.dispose()
            print('closed db connection successfully')
    except Exception as err:
        print('failed to connect to FPS database')
        raise err

    return data

def read_system_parameters():
    '''Find the current system parameters'''
    # establish FPS database connection
    try:
        connection, cnx = database_connection()
        print('FPS db connection successful')
        # get vehicle id from t_vehicle table
        print('reading from system_parameters table')
        try:
            system_parameters = pd.read_sql(
                'SELECT * FROM t_system_parameters', connection)
            print('system_parameters read successful')
        except sqlalchemy.exc.OperationalError as err:
            print('system_parameters read unsuccessful')
            raise err
        except ValueError as err:
            print('system_parameters read unsuccessful')
            raise err
        finally:
            # close the db connection
            connection.close()
            cnx.dispose()
            print('closed db connection successfully')
    except Exception as err:
        print('failed to connect to FPS database')
        raise err

    return system_parameters

def upload_to_database(input_data, table):
    '''Append the given data to the specified database table'''
    # establish FPS database connection
    try:
        connection, cnx = database_connection()
        print('FPS db connection successful')
        print('writing data to table')
        try:
            input_data.to_sql(table, con=cnx,
                              if_exists='append', index=False)
            print('data write successful')
        except sqlalchemy.exc.OperationalError as err:
            print('data write unsuccessful')
            raise err
        except ValueError as err:
            print('data write unsuccessful')
            raise err
        finally:
            # close the db connection
            connection.close()
            cnx.dispose()
            print('closed db connection successfully')
    except Exception as err:
        print('failed to connect to FPS database')
        raise err
    
    
def update_value(table, key_col, key_val, data_col, data_val):
    '''Update value in selected column where row is contains given key value
    Args:
        table (str): table name to read data from
        key_col (str): column name to specify keys from
        key_val (singleton): value of key_col to access the row of
        data_col (str): column name to change value of
        data_val (singleton): value to update data_col with'''
    # establish FPS database connection
    print('here 1')
    query_str = ('UPDATE ' + table
                 + ' SET ' + data_col + ' = (%s)'
                 + ' WHERE ' + key_col + ' = (%s)')

    # establish FPS database connection
    try:
        connection, cnx = database_connection()
        cursor = connection.cursor()
        print('FPS db connection successful')
        try:
            print('here 2')
            cursor.execute(query_str, (data_val, key_val))
            print('query_str = ' + query_str)
            print('(key_val, data_val) = ' + str((data_val, key_val)))
            connection.commit()
            print('data read successful')
        except sqlalchemy.exc.OperationalError as err:
            print('data read unsuccessful')
            raise err
        except ValueError as err:
            print('data read unsuccessful')
            raise err
        finally:
            # close the db connection
            cursor.close()
            connection.close()
            cnx.dispose()
            print('closed db connection successfully')
    except Exception as err:
        print('failed to connect to FPS database')
        raise err



# the main calculation function
# Bill editing
# failed_uploads = []
# successful_uploads = []

# don't rank which should be passed to charge scheduling as default 
decide_scheduling = False

# # find the current run_id FOR END TO END MODEL RUNS ONLY
# run_id = read_input_data('t_system_parameters', 'parameter_name', 'current_run_id')
# run_id = int(run_id['parameter_value'].item())

# read fuel cabron intensities
diesel_gco_litre = read_input_data('t_system_parameters', 'parameter_name', 'diesel_gco_litre')
diesel_gco_litre = int(diesel_gco_litre['parameter_value'].item())
petrol_gco_litre = read_input_data('t_system_parameters', 'parameter_name', 'petrol_gco_litre')
petrol_gco_litre = int(petrol_gco_litre['parameter_value'].item())
grid_gco_kwh = read_input_data('t_system_parameters', 'parameter_name', 'grid_gco_kwh')
grid_gco_kwh = int(grid_gco_kwh['parameter_value'].item())

# get the inputs for this run
inputs = read_input_data('t_run_vehicle_tco', 'run_id', run_id)
# read the macro assumptions
lifetime = inputs['asset_lifetime'].item()
# interest rate (annual)
interest_rate = inputs['interest_rate'].item()
# finance period (months)
finance_period = inputs['finance_period'].item()
# upfront lease payment
upfront_lease = inputs['upfront_lease'].item()
# use a time of use tariff or not
tou_tariff = inputs['tou_tariff'].item()
# £/kwh price to use for a flat tariff
flat_tariff = inputs['flat_tariff_rate'].item()
# find the fossil fuel costs
petrol_cost = inputs['petrol_cost'].item()
diesel_cost = inputs['diesel_cost'].item()
# find the non-fuel vehicle costs
ved = inputs['ved'].item()
insurance = inputs['insurance'].item()
tyre_cost = inputs['tyre_cost_rate'].item()
maintenance = inputs['maintenance_rate'].item()
ev_maintenance_disc = inputs['ev_maintenance_discount'].item()
# find the annual mileage bands for residual value lookup
mileage_thresholds = inputs['mileage_thresholds'].item()
mileage_thresholds = mileage_thresholds.split(', ')
mileage_thresholds = [int(i) for i in mileage_thresholds]

# # find the client id FOR END TO END MODEL RUNS ONLY
# client_id = read_input_data('t_run_master', 'run_id', run_id)
# client_id = client_id['client_id'].item()

# get allocations for this run id
allocation_info_all = read_input_data('t_allocation', 'run_id', run_id)
# find the unique site ids for this run
site_ids = pd.unique(allocation_info_all['site_id']).tolist()

# site_ids = [6, 12, 3, 4, 5, 7, 10, 20, 2, 11, 21, 23]
# site_ids = [4, 5, 7, 10, 20, 2, 11, 21, 23]
# site_ids = [23]

# for each site
for site_id in site_ids:
    # get site mileage conversion factor DON'T USE THIS ONE, TAKE xmpg FROM t_allocation
    site_info = read_input_data('t_sites', 'site_id', site_id)
    # find the allocation_ids for this site id
    allocation_ids = allocation_info_all[
        allocation_info_all['site_id']==site_id]['allocation_id'].tolist()
    schedule_ids = allocation_info_all[
        allocation_info_all['site_id']==site_id]['schedule_charge'].tolist()
    # remove ids which should not be analysed based on schedule_charge flag
    allocation_ids = [allocation_ids[x] for x in
                      range(0, len(allocation_ids)) if schedule_ids[x] > 0]
    print(allocation_ids)

    for allocation_id in allocation_ids:
        # get allocation run info
        allocation_info = allocation_info_all[
            allocation_info_all['allocation_id']==allocation_id]
        # get site mileage conversion factor
        xmpg = allocation_info['xmpg'].item()
        # extract variable indicating which stage of allocation processing
        schedule_charge = allocation_info['schedule_charge'].item()
        # get the allocated routes
        allocated_routes = read_input_data('t_route_allocated',
                                           'allocation_id', allocation_id)
        # find the unique vehicles
        allocated_vehicle_ids = allocated_routes['allocated_vehicle_id'].to_numpy()
        allocated_spec_ids = allocated_routes['allocated_spec_id'].to_numpy()
        # extract the unique vehicle ids and matching spec ids
        allocated_vehicle_ids, idx = np.unique(allocated_vehicle_ids,
                                                return_index=True)
        allocated_spec_ids = allocated_spec_ids[idx]
        # for each unique vehicle spec lookup: purchase price, PIVG, energy/petrol use, maintenance saving
        unique_spec_ids = np.unique(allocated_spec_ids)
        unique_spec_ids = tuple(unique_spec_ids.tolist())
        vehicle_specs = read_input_data('t_vehicle_specification', 'spec_id', unique_spec_ids)
        # get the full route data for all routes allocated on this id
        unique_routes = np.unique(allocated_routes['route_id'])
        unique_routes = tuple(unique_routes.tolist())
        
        # synthetic_routes = read_input_data('t_route_synthetic', # SYNTHETIC ROUTES REMOVED FROM WORKFLOW
        #                                    'synthetic_route_id',
        #                                    unique_routes)
        
        synthetic_routes = read_input_data('t_route_master', # USE HISTORIC FROM t_route_master INSTEAD OF SYNTHETIC ROUTES
                                           'route_id',
                                           unique_routes)
        synthetic_routes.rename(columns={'route_id': 'synthetic_route_id'}, inplace=True)
        
        # merge with data from t_route_allocation on the route id 
        complete_routes = pd.merge(allocated_routes, synthetic_routes,
                                   how='outer', left_on=['route_id'],
                                   right_on=['synthetic_route_id'])
        
        # group mileages by the vehicle id
        vehicle_mileages = complete_routes.groupby("allocated_vehicle_id")["distance_miles"].sum()
        # find the factor to mutiply up by to get annualised results THIS WILL ERRONEOUSLY INCREASE RESULTS IF NO OPERATIONS PURPOSELY OCCUR AT START OR END OF DATE RANGE
        # find the number of days that each vehicle operates on, and the start and end dates
        complete_routes['dayofyear'] = complete_routes['departure_time'].dt.dayofyear+(complete_routes['departure_time'].dt.year*365)
        vehicle_minday = complete_routes.groupby("allocated_vehicle_id")["dayofyear"].min()
        vehicle_minday = vehicle_minday.rename('vehicle_minday')
        vehicle_maxday = complete_routes.groupby("allocated_vehicle_id")["dayofyear"].max()
        vehicle_maxday = vehicle_maxday.rename('vehicle_maxday')
        vehicle_mindate = complete_routes.groupby("allocated_vehicle_id")["departure_time"].min()
        vehicle_mindate = vehicle_mindate.rename('vehicle_mindate')
        vehicle_maxdate = complete_routes.groupby("allocated_vehicle_id")["departure_time"].max()
        vehicle_maxdate = vehicle_maxdate.rename('vehicle_maxdate')
        # add to the mileage df
        vehicle_mileages = vehicle_mileages.to_frame()
        vehicle_mileages['vehicle_minday'] = vehicle_minday
        vehicle_mileages['vehicle_maxday'] = vehicle_maxday
        vehicle_mileages['vehicle_mindate'] = vehicle_mindate
        vehicle_mileages['vehicle_maxdate'] = vehicle_maxdate
        # find and apply the annualise factor
        vehicle_mileages['ndays'] = vehicle_mileages['vehicle_maxday'] - (vehicle_mileages['vehicle_minday'] - 1)
        vehicle_mileages['annualise_factor'] = 1/(vehicle_mileages['ndays']/365)
        vehicle_mileages['distance_miles'] = vehicle_mileages['distance_miles']*vehicle_mileages['annualise_factor']
        # band the annual mileage of each vehicle
        vehicle_mileage_band = np.zeros(len(vehicle_mileages))
        for i_band in range(0, len(mileage_thresholds)):
            thresh = mileage_thresholds[i_band]
            vehicle_mileage_band = (vehicle_mileage_band
                                    + (vehicle_mileages['distance_miles'] >= thresh).astype(int))
        vehicle_mileage_band = vehicle_mileage_band - 1
        # read the residual value lookup table
        vehicle_categories = vehicle_specs['vehicle_category'].unique()
        vehicle_categories = tuple(vehicle_categories.tolist())
        residual_value_lookup = read_input_data('t_residual_values',
                                                'vehicle_category',
                                                vehicle_categories)
        # read the capital allowances lookup table
        capital_allowance_lookup = read_input_data('t_capital_allowances',
                                                'vehicle_category',
                                                vehicle_categories)
        
        # create TCO components dataframe
        tco_calc = vehicle_mileages
        tco_calc['spec_id'] = allocated_spec_ids
        tco_calc['mileage_band'] = vehicle_mileage_band
        tco_calc['lifetime'] = lifetime
        tco_calc['interest_rate'] = interest_rate
        tco_calc['finance_period'] = finance_period
        tco_calc['upfront_lease'] = upfront_lease
        # tco_calc['insurance'] = insurance OLD RETAIN FOR FIRST TEST
        tco_calc['tyre_cost'] = tyre_cost*tco_calc['distance_miles']
        tco_calc['client_id'] = client_id
        tco_calc = tco_calc.reset_index()
        

        # preliminary TCO calculation before charge scheduling
        if schedule_charge == 1:
            # set dummy scenario ids
            scenario_ids = [-1]
        # final TCO calculation after charge scheduling
        elif schedule_charge == 2:
            scenario_info_all = read_input_data('t_charging_scenarios',
                                                'allocation_id',
                                                allocation_id)
            scenario_ids = scenario_info_all['scenario_id'].tolist()
            # # avoid infeasible scenarios pick first SHORT TERM WORLFOW CHANGE
            # scenario_ids.sort()
            # scenario_ids = scenario_ids[0:1]
        # for each charging scenario
        for i_scenario in range(0, len(scenario_ids)):
            scenario_id = scenario_ids[i_scenario]
            # remove scenario ids which should not be run based on schedule_charge flag NOT REQUIRED AS ONLY RUNNING FIRST SCENARIO
            
            # merge tco components with the vehicle specs
            tco_calc_full = tco_calc.copy(deep=True)
            tco_calc_full = pd.merge(tco_calc_full,vehicle_specs,how='outer',left_on=['spec_id'],right_on=['spec_id'])
            # preliminary TCO calculation before charge scheduling
            if schedule_charge == 1:
                preliminary_tco_lease = allocation_info['preliminary_tco_lease'].item()
                preliminary_tco_purchase = allocation_info['preliminary_tco_purchase'].item()

                tco_calc_full['fuel_cost'] = 0
                # fuel costs accounting for site xmpg efficiency
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'fuel_cost'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'distance_miles']
                                                                                            *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'energy_use']
                                                                                            *flat_tariff)/xmpg
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'fuel_cost'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'distance_miles']
                                                                                          *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'energy_use']
                                                                                          *diesel_cost)/xmpg
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'fuel_cost'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'distance_miles']
                                                                                          *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'energy_use']
                                                                                          *petrol_cost)/xmpg
            # final TCO calculation after charge scheduling
            elif schedule_charge == 2:
                if tou_tariff == 1:
                    # find the dno region and corresponding tariff
                    dno_id = site_info['distribution_id'].item()
                    tariff_data = read_input_data('t_electricity_price',
                                                'distribution_id',
                                                dno_id)
                    # read the timeseries charge profiles
                    scenario_info = scenario_info_all[
                                    scenario_info_all['scenario_id'] == scenario_id]
                    charge_profiles = read_input_data('t_charge_demand',
                                                    'scenario_id',
                                                    scenario_id)
                    charge_profiles = pd.merge(charge_profiles,tariff_data,how='outer',left_on=['datetime'],right_on=['datetime'])
                    # drop the tariff only datetime rows for which there is no charge profile
                    charge_profiles = charge_profiles.dropna(subset=['allocated_vehicle_id'])
                    # find the fuel cost for each half hour, accounting for the fuel efficiency of the site
                    charge_profiles['fuel_cost'] = charge_profiles['electricity_price_fixed']*charge_profiles['power_demand_kw']/(2*xmpg)
                    ev_fuel_cost = charge_profiles.groupby("allocated_vehicle_id")["fuel_cost"].sum()
                    ev_fuel_cost = ev_fuel_cost.rename("fuel_cost")
                    ev_fuel_cost = ev_fuel_cost.reset_index()
                    # annualise results
                    tco_calc_full = pd.merge(tco_calc_full,ev_fuel_cost,how='outer',left_on=['allocated_vehicle_id'],right_on=['allocated_vehicle_id'])
                    tco_calc_full['fuel_cost'] = tco_calc_full['fuel_cost']*tco_calc_full['annualise_factor']
                
                else:
                    tco_calc_full['fuel_cost'] = 0
                    # fuel costs accounting for site xmpg efficiency
                    tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'fuel_cost'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'distance_miles']
                                                                                                *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'energy_use']
                                                                                                *flat_tariff)/xmpg
                # add the ice vehicle fuel costs accounting for site xmpg efficiency
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'fuel_cost'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'distance_miles']
                                                                                          *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'energy_use']
                                                                                          *diesel_cost)/xmpg
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'fuel_cost'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'distance_miles']
                                                                                          *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'energy_use']
                                                                                          *petrol_cost)/xmpg

    
            # add the vehicle maintenance costs
            tco_calc_full['maintenance_pct'] = 1
            tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric','maintenance_pct'] = 1 - ev_maintenance_disc
            # tco_calc_full['ved'] = ved OLD RETAIN FOR FIRST TEST
            tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric','ved'] = 0
            tco_calc_full['maintenance'] = maintenance*tco_calc_full['distance_miles']*tco_calc_full['maintenance_pct']
            tco_calc_full_tmp = tco_calc_full.copy(deep=True)
            # find residual value
            tco_calc_full = pd.merge(tco_calc_full,residual_value_lookup,
                                how='inner',left_on=['vehicle_category', 'lifetime', 'mileage_band'],
                                right_on=['vehicle_category', 'lifetime', 'mileage_band'])
            # find capital allowance
            tco_calc_full = pd.merge(tco_calc_full,capital_allowance_lookup,
                                how='inner',left_on=['vehicle_category', 'lifetime', 'capital_allowance_rate'],
                                right_on=['vehicle_category', 'lifetime', 'capital_allowance_rate'])
            # # adjust for EVs
            # tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'accumulated_capital_allowance'] = 0.19
            # calculate net vehicle cost
            tco_calc_full['net_purchase_cost'] = tco_calc_full['vehicle_purchase_price'] - tco_calc_full['pivg']
            # calculate capital allowance
            tco_calc_full['full_capital_allowance'] = tco_calc_full['accumulated_capital_allowance']*tco_calc_full['net_purchase_cost']
            # calculate residual value
            tco_calc_full['full_residual_value'] = tco_calc_full['residual_value_pct']*tco_calc_full['vehicle_purchase_price']

            
            # calculate the annual lease payments
            tco_calc_full['annual_lease_payments'] = -12*npf.pmt((tco_calc_full['interest_rate']/12).to_numpy(), tco_calc_full['finance_period'].to_numpy(),
                    (tco_calc_full['net_purchase_cost']*(1-tco_calc_full['upfront_lease'])).to_numpy(), fv=-tco_calc_full['full_residual_value'].to_numpy(), when=0)
            # calculate the TCO
            tco_calc_full['total_cost_ownership'] = (tco_calc_full['net_purchase_cost'] - tco_calc_full['full_capital_allowance'] - tco_calc_full['full_residual_value']
                            + tco_calc_full['lifetime']*(tco_calc_full['fuel_cost'] + tco_calc_full['ved'] + tco_calc_full['insurance'] + tco_calc_full['tyre_cost'] + tco_calc_full['maintenance']))
            tco_calc_full['annualised_ownership_cost'] = tco_calc_full['total_cost_ownership']/tco_calc_full['lifetime']
            tco_calc_full['annual_costs_lease'] = (tco_calc_full['annual_lease_payments'] + tco_calc_full['fuel_cost'] + tco_calc_full['ved'] + tco_calc_full['insurance'] + tco_calc_full['tyre_cost'] + tco_calc_full['maintenance'])
            tco_calc_full['upfront_cost_lease'] = tco_calc_full['net_purchase_cost']*tco_calc_full['upfront_lease']
            
            # preliminary TCO calculation before charge scheduling
            if schedule_charge == 1:
                # find costs for leasing assets
                vehicle_cost = (tco_calc_full['annual_costs_lease']
                                * tco_calc_full['lifetime']
                                + tco_calc_full['upfront_cost_lease']).sum()
                scenario_cost = preliminary_tco_lease + vehicle_cost
                # update table
                update_value('t_allocation', 'allocation_id', allocation_id,
                            'preliminary_tco_lease', scenario_cost)
                # find costs for purchasing assets
                vehicle_cost = (tco_calc_full['annualised_ownership_cost']
                                * tco_calc_full['lifetime']).sum()
                scenario_cost = preliminary_tco_purchase + vehicle_cost
                # update table
                update_value('t_allocation', 'allocation_id', allocation_id,
                            'preliminary_tco_purchase', scenario_cost)
                # if the prelim TCO already had a vehicle costs then app needs to decide scheduling
                if preliminary_tco_lease != 0:
                    decide_scheduling = True
            
            # find the annual carbon emissions
            tco_calc_full['scope_1_emissions'] = 0
            tco_calc_full['scope_2_emissions'] = 0
            tco_calc_full['scope_3_emissions'] = 0
            tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'scope_1_emissions'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'distance_miles']
                                                                                            *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'diesel', 'energy_use']
                                                                                            *diesel_gco_litre)/xmpg
            tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'scope_1_emissions'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'distance_miles']
                                                                                            *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'petrol', 'energy_use']
                                                                                            *petrol_gco_litre)/xmpg
            tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'scope_2_emissions'] = (tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'distance_miles']
                                                                                                *tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'energy_use']
                                                                                                *grid_gco_kwh)/xmpg
            
            # final TCO calculation after charge scheduling
            if schedule_charge == 2:
                tco_calc_full['scenario_id'] = scenario_id
                tco_calc_full['allocation_id'] = allocation_id
                tco_calc_full['run_id'] = run_id
                tco_calc_full['client_id']
                tco_calc_full['site_id'] = allocation_info['site_id'].item()

                tco_calc_full.rename(columns={"allocated_vehicle_id": "vehicle_id",
                                            "distance_miles": "annual_mileage",
                                            "vehicle_purchase_price": "purchase_price",
                                            "net_purchase_cost": "purchase_price_w_grant",
                                            "upfront_cost_lease": "upfront_lease_cost",
                                            "tyre_cost": "annual_tyre_cost",
                                            "ved": "annual_ved",
                                            "insurance": "annual_insurance"},
                                    inplace = True)
                tco_calc_full_tmpp = tco_calc_full.copy(deep = True)
                # separate out ice vehicle fuel costs
                tco_calc_full['annual_fuel_cost'] = tco_calc_full['fuel_cost']
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'annual_fuel_cost'] = 0
                # separate out EV fuel costs
                tco_calc_full['annual_electricity_cost'] = 0
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'annual_electricity_cost'] = tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'fuel_cost']
                # separate out ice vehicle maintenance costs
                tco_calc_full['annual_ice_maintenance'] = tco_calc_full['maintenance']
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'annual_ice_maintenance'] = 0
                # separate out ev maintenance costs
                tco_calc_full['annual_ev_maintenance'] = 0
                tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'annual_ev_maintenance'] = tco_calc_full.loc[tco_calc_full['fuel_type'] == 'electric', 'maintenance']

                # keep only the necessary columns
                final_table_columns = ['scenario_id', 'allocation_id', 'run_id', 'client_id',
                                    'site_id', 'vehicle_id', 'spec_id', 'annual_mileage',
                                    'mileage_band', 'fuel_type', 'purchase_price',
                                    'purchase_price_w_grant', 'upfront_lease_cost',
                                    'annual_fuel_cost', 'annual_electricity_cost',
                                    'annual_ice_maintenance', 'annual_ev_maintenance',
                                    'annual_tyre_cost', 'annual_ved', 'annual_insurance',
                                    'scope_1_emissions', 'scope_2_emissions',
                                    'scope_3_emissions', 'annualise_factor',
                                    'vehicle_mindate', 'vehicle_maxdate']
                tco_calc_full.drop(columns=tco_calc_full.columns.difference(final_table_columns), inplace=True)
                # upload the tco components
                try:
                    upload_to_database(tco_calc_full, 't_vehicle_tco_components')
                    successful_uploads.append([site_id, allocation_id, scenario_id])
                    print('SUCCESS ' + str(scenario_id) + ', ' + str(allocation_id) + ', ' + str(site_id))
                except:
                    failed_uploads.append([site_id, allocation_id, scenario_id])
                    print('FAIL ' + str(scenario_id) + ', ' + str(allocation_id) + ', ' + str(site_id))
        
