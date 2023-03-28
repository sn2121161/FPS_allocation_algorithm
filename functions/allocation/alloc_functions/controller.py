# This module takes the run inputs and creates a master allocation table

import pandas as pd
import os
import psycopg2
import sqlalchemy
import datetime as dt
import json
import pipeline_plan_functions.utils.pipe_db_handler as dbh
import pipeline_plan_functions.utils.data_types as dth
import pipeline_plan_functions.utils.data_handler as dh
from python_utils.utils.logger import logger
logger.setLevel(os.getenv('log_level', "DEBUG"))


DEFAULT_DIESEL = 28


def find_site_vehicle_category(site, connection, cur):
    # Find site data
    try:
        sql_query = ("SELECT vehicle_category "
                     f"FROM t_sites WHERE site_id={site}")
        cur.execute(sql_query)
        connection.commit()
        category = cur.fetchall()[0][0]
    except (Exception, psycopg2.Error) as error:
        logger.error(f"Error while fetching vehicle category for site {site}")
        raise error
    return category


def vehicles_bycategory(category, connection, cur):
    try:
        sql_query = f"""SELECT spec_id FROM t_vehicle_specification
            WHERE vehicle_category='{category}' AND fuel_type='electric'"""
        cur.execute(sql_query)
        connection.commit()
        category_fetch = cur.fetchall()
        vehicles = [vehicle[0] for vehicle in category_fetch]
    except (Exception, psycopg2.Error) as error:
        logger.error(f"Error while fetching {category} vehicles")
        raise error
    return vehicles


def get_fps_allocation_id(connection, cur):
    '''Return the largest currently assigned fps allocation id'''
    # establish FPS database connection
    query_str = ('SELECT allocation_id FROM t_allocation '
                 'ORDER BY allocation_id DESC LIMIT 1')
    logger.debug('reading last allocation ID')
    allocation_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        allocation_id = cur.fetchall()[0][0]
    except sqlalchemy.exc.OperationalError as err:
        logger.info('allocation info read unsuccessful')
        raise err
    except ValueError as err:
        logger.info('allocation infos read unsuccessful')
        raise err
    except IndexError as err:
        logger.info(f'No allocation ID in t_allocation {err}')
    return allocation_id


def create_allocation_table(inputs, connection, cur):
    if inputs['sites'] is None:
        client = inputs['client_id']
        sites = dh.get_sites(client, connection, cur)
    else:
        sites = json.loads(inputs['sites'])
    alloc_cols = [
        'run_id', 'allocation_id', 'site_id', 'start_date', 'end_date',
        'xmpg_change', 'vehicle_pool', 'charger1', 'charger2', 'route_table',
        'source', 'num_v']
    df = pd.DataFrame(columns=alloc_cols)
    df['site_id'] = sites
    for c in ['run_id', 'start_date', 'end_date', 'xmpg_change', 'route_table',
              'cap_vehicles', 'source', 'num_v']:
        df[c] = inputs[c]
    largest_allocation_id = get_fps_allocation_id(connection, cur)
    df['allocation_id'] = df.index + largest_allocation_id + 1
    df['charger1'], df['charger2'] = dth.separate_chargers(inputs['chargers'])
    df['vehicle_pool'] = inputs['vehicles']
    df['allocated'] = 'n'
    # TODO add a set here to asign different vehicles per row if necessary
    return df


def select_vehicles(site, alloc_vehicles, connection, cur,
                    default_diesel=DEFAULT_DIESEL):
    if alloc_vehicles == 'electric':
        # Find vehicles per site
        category = find_site_vehicle_category(site, connection, cur)
        vehicles = [vehicles_bycategory(category, connection, cur), []]
    elif alloc_vehicles == 'mixed':
        category = find_site_vehicle_category(site, connection, cur)
        vehicles = [vehicles_bycategory(category, connection, cur),
                    [default_diesel]]
    else:
        vehicles = json.loads(alloc_vehicles)
    return vehicles


def main(run):
    try:
        logger.info(f"Allocation app called at {dt.datetime.now()}")
        connection, cur = dbh.database_connection('test')
        # cnx = dbh.create_alch_engine()
        if run is None:
            # FIND THE MOST UP TO DATE RUN ID
            run = dh.get_current_run(connection, cur)
        # Get run input parameters
        inputs = dh.get_inputs('t_run_allocation', run, connection, cur)
        # Select sites, if None, do all sites for that client ID, Create DF
        df = create_allocation_table(inputs, connection, cur)
        # Select vehicle pool, if None, assign vehicles according to their
        # classification
        for idx in df.index:
            vehicle_pool = select_vehicles(
                df.loc[idx, 'site_id'], df.loc[idx, 'vehicle_pool'],
                connection, cur)
            # Order vehicles
            if len(vehicle_pool[0]) > 1:
                vehicle_pool[0] = dh.order_items(
                    vehicle_pool[0], 't_vehicle_specification', 'spec_id',
                    'vehicle_purchase_price',  connection, cur)
            df.at[idx, 'vehicle_pool'] = vehicle_pool
        df['vehicle_pool'] = df['vehicle_pool'].astype(str)
        # Output to t_allocation
        dbh.upload_table(df, 't_allocation')
    except Exception as e:
        logger.error(e)
        SystemExit(e)
    finally:
        cur.close()
        connection.close()
        logger.info("Closed db connection")
    return df['allocation_id'].values
    # TODO read a list of lists for vehicles and chargers


if __name__ == '__main__':
    main(25)
