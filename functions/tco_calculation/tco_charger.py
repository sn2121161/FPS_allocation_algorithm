import pandas as pd
import datetime as dt
import logging
import os
import psycopg2
import sqlalchemy
import numpy as np
import numpy_financial as npf


run_id = 215 # USER INPUT: SET A DESIRED RUN ID HERE
client_id = 2 # USER INPUT: SET CLIENT ID HERE

# database related
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
    ssl_mode = os.getenv('pipe_ssl_mode', '')
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
    # build the query string
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
    
# ?
failed_uploads = []
successful_uploads = []

# don't rank which should be passed to charge scheduling as default 
decide_scheduling = False

# # find the current run_id FOR END TO END MODEL RUNS ONLY
# run_id = read_input_data('t_system_parameters', 'parameter_name', 'current_run_id')
# run_id = int(run_id['parameter_value'].item())

# get the inputs for this run
inputs = read_input_data('t_run_charger_tco', 'run_id', run_id)
# find the capital allowance
capital_allowance_pct = inputs['capital_allowance'].item()
lifetime = inputs['asset_lifetime'].item() # UNUSED
# interest rate
interest_rate = inputs['interest_rate'].item() # UNUSED
# finance period
finance_period = inputs['finance_period'].item() # UNUSED
# upfront lease payment
upfront_lease = inputs['upfront_lease'].item()

# # find the client id FOR END TO END MODEL RUNS ONLY
# client_id = read_input_data('t_run_master', 'run_id', run_id)
# client_id = client_id['client_id'].item()

# main fuction
def build_tco_components(charger_a_rating, charger_b_rating,
                         charger_a_count, charger_b_count):
    '''Build a dataframe containing all charger TCO components
    Args:
        charger_a_rating (float): the rating in kW of chargers a
        charger_b_rating (float): the rating in kW of chargers b
        charger_a_count (int): the number of chargers a
        charger_b_count (int): the number of chargers b
    Returns:
        tco_components (dataframe): the components of charger TCO analysis'''
    # get the possible charger specifications
    charger_a_specs = read_input_data('t_charger_specification',
                                    'power',
                                    charger_a_rating)
    charger_b_specs = read_input_data('t_charger_specification',
                                    'power',
                                    charger_b_rating)

    # find the costs for this unit purchase size
    charger_a_specs.sort_values(by=['n_units_min'], inplace=True, ignore_index=True)
    charger_a_indx = sum(charger_a_specs['n_units_min'] <= charger_a_count)-1
    charger_a_spec = charger_a_specs.loc[charger_a_indx]
    charger_b_specs.sort_values(by=['n_units_min'], inplace=True, ignore_index=True)
    # print(charger_b_specs)
    # print(charger_b_specs['n_units_min'])
    # print(charger_b_count)
    # print(charger_b_specs['n_units_min'] <= charger_b_count)
    # print(sum(charger_b_specs['n_units_min'] <= charger_b_count))
    charger_b_indx = sum(charger_b_specs['n_units_min'] <= charger_b_count)-1
    charger_b_spec = charger_b_specs.loc[charger_b_indx]

    # for each charger type find number of units and power rating
    charger_units = np.array([charger_a_count, charger_b_count])
    charger_power = np.array([charger_a_rating, charger_b_rating])
    # find the unit cost (lookup includes installation cost)
    purchase_price = np.array(
        [int(charger_a_spec['per_unit_cost'].item()),
        int(charger_b_spec['per_unit_cost'].item())])*charger_units
    # find the annual monitoring cost
    annual_monitoring_cost = np.array(
        [charger_a_spec['monitoring_cost'].item(),
        charger_b_spec['monitoring_cost'].item()])*charger_units
    # find the annual optimisation cost
    annual_optimsation_cost = np.array(
        [charger_a_spec['optimisation_cost'].item(),
        charger_b_spec['optimisation_cost'].item()])*charger_units
    # find the annual maintenance cost
    annual_maintenance_cost = np.array(
        [charger_a_spec['maintenance_cost'].item(),
        charger_b_spec['maintenance_cost'].item()])*charger_units
    # find the unit grant
    charger_purchase_grant = np.array(
        [charger_a_spec['grant'].item(),
        charger_b_spec['grant'].item()])*charger_units
    # net unit cost
    purchase_price_w_grant = purchase_price - charger_purchase_grant
    # upfront lease cost
    upfront_lease_cost = purchase_price_w_grant*upfront_lease
    # site id
    site_id_data = np.array([site_id, site_id])
    # allocation id
    allocation_id_data = np.array([allocation_id, allocation_id])
    # client id
    client_id_data = np.array([client_id, client_id])
    # run id
    run_id_data = np.array([run_id, run_id])

    tco_components = pd.DataFrame({'n_units': charger_units,
                                    'power': charger_power,
                                    'purchase_price': purchase_price,
                                    'annual_monitoring_cost': annual_monitoring_cost,
                                    'annual_optimisation_cost': annual_optimsation_cost,
                                    'annual_maintenance_cost': annual_maintenance_cost,
                                    'purchase_price_w_grant': purchase_price_w_grant,
                                    'upfront_lease_cost': np.round(upfront_lease_cost),
                                    'site_id': site_id_data,
                                    'allocation_id': allocation_id_data,
                                    'client_id': client_id_data,
                                    'run_id': run_id_data})
    return tco_components


# get allocations for this run id
allocation_info_all = read_input_data('t_allocation', 'run_id', run_id)
# find the unique site ids for this run
site_ids = pd.unique(allocation_info_all['site_id']).tolist()
# for each site
for site_id in site_ids:
    # find the allocation_ids for this site id
    allocation_ids = allocation_info_all[
        allocation_info_all['site_id']==site_id]['allocation_id'].tolist()
    for allocation_id in allocation_ids:
        # get allocation run info
        allocation_info = allocation_info_all[
            allocation_info_all['allocation_id']==allocation_id]
        schedule_charge = allocation_info['schedule_charge'].item()
        # preliminary TCO calculation before charge scheduling, flag set in t_allocation
        if schedule_charge == 1:
            preliminary_tco_lease = allocation_info['preliminary_tco_lease'].item()
            preliminary_tco_purchase = allocation_info['preliminary_tco_purchase'].item()

            charger_a_rating = allocation_info['charger1'].item()
            charger_b_rating = allocation_info['charger2'].item()
            charger_a_count = allocation_info['num_charger1'].item()
            charger_b_count = allocation_info['num_charger2'].item()
            
            tco_components = build_tco_components(charger_a_rating,
                                                  charger_b_rating,
                                                  charger_a_count,
                                                  charger_b_count)
            purchase_price_w_grant = tco_components['purchase_price_w_grant'].to_numpy()
            # add capital allowance
            purchase_price_w_grant = (1-capital_allowance_pct)*purchase_price_w_grant
            annual_maintenance_cost = tco_components['annual_maintenance_cost'].tolist()

            # calculate costs for purchasing
            charger_cost = (sum(purchase_price_w_grant)
                            + sum(annual_maintenance_cost))
            scenario_cost = preliminary_tco_lease + charger_cost
            # update table
            update_value('t_allocation', 'allocation_id', allocation_id,
                        'preliminary_tco_lease', scenario_cost)
            
            scenario_cost = preliminary_tco_purchase + charger_cost
            # update table
            update_value('t_allocation', 'allocation_id', allocation_id,
                        'preliminary_tco_purchase', scenario_cost)
            # if the prelim TCO already had a vehicle costs then app needs to decide scheduling CURRENTLY DECIDED MANUALLY
            if preliminary_tco_purchase != 0:
                decide_scheduling = True
                
        # final TCO calculation after charge scheduling creating results for dashboard, flag set in t_allocation
        elif schedule_charge == 2:
            # find the charging scenarios for this allocation
            scenario_info_all = read_input_data('t_charging_scenarios',
                                                'allocation_id',
                                                allocation_id)
            scenario_ids = scenario_info_all['scenario_id'].tolist()
            for i_scenario in range(0, len(scenario_ids)):
                scenario_id = scenario_ids[i_scenario]

                scenario_info = scenario_info_all[
                    scenario_info_all['scenario_id'] == scenario_id]
                
                charger_a_rating = scenario_info['charger1'].item()
                charger_b_rating = scenario_info['charger2'].item()
                charger_a_count = scenario_info['num_charger1'].item()
                charger_b_count = scenario_info['num_charger2'].item()
                
                tco_components = build_tco_components(charger_a_rating,
                                                      charger_b_rating,
                                                      charger_a_count,
                                                      charger_b_count)
        
                tco_components['scenario_id'] = scenario_id


                # try to upload to results to the database
                try: 
                    upload_to_database(tco_components, 't_charger_tco_components')
                    successful_uploads.append([site_id, allocation_id, scenario_id])
                    print('SUCCESS ' + str(scenario_id) + ', ' + str(allocation_id) + ', ' + str(site_id))
                except:
                    failed_uploads.append([site_id, allocation_id, scenario_id])
                    print('FAIL ' + str(scenario_id) + ', ' + str(allocation_id) + ', ' + str(site_id))
