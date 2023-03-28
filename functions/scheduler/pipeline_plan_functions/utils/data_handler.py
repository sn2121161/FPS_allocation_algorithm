# There are all functions reading from the datase

import os
import sys
import pandas as pd
import psycopg2
import sqlalchemy
from python_utils.utils.logger import logger
import pipe_db_handler as dbh

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CDIR)


def get_current_run(connection, cur):
    try:
        sql_query = """SELECT parameter_value FROM t_system_parameters
            WHERE parameter_name='current_run_id'"""
        cur.execute(sql_query)
        connection.commit()
        run = int(cur.fetchall()[0][0])
        logger.debug(f"Current run {run}")
    except (Exception, psycopg2.Error) as error:
        logger.error("No valid current run ID")
        raise error
    return run


def get_inputs(table, run, connection, cur):
    try:
        sql_query = f"""SELECT * FROM {table} WHERE run_id={run}"""
        cur.execute(sql_query)
        connection.commit()
        desc = cur.description
        values = cur.fetchall()[0]
        column_names = [col[0] for col in desc]
        inputs = dict(zip(column_names, values))
        logger.debug(f"read inputs for run {run}")
    except (Exception, psycopg2.Error) as error:
        logger.error(f"No inputs in {table}")
        raise error
    return inputs


def get_fps_route_id(connection, cur):
    '''Return the largest currently assigned fps route id'''
    # establish FPS database connection
    query_str = (
        'SELECT route_id FROM t_route_master ORDER BY route_id DESC LIMIT 1')
    query_2 = (
        'SELECT route_id FROM t_telematics ORDER BY route_id DESC LIMIT 1')
    logger.info('reading formatted routing data from t_routing table')
    route_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        route_id_routes = cur.fetchall()[0][0]
        cur.execute(query_2)
        connection.commit()
        route_id_tel = cur.fetchall()[0][0]
        route_id = max(route_id_routes, route_id_tel)
    except sqlalchemy.exc.OperationalError as err:
        logger.info('spec infos read unsuccessful')
        raise err
    except ValueError as err:
        logger.info('spec infos read unsuccessful')
        raise err
    except IndexError:
        logger.info('No route ID in t_route_master')
    return route_id


def get_fps_node_id(connection, cur):
    '''Return the largest currently assigned fps route id'''
    # establish FPS database connection
    query_str = ('SELECT journey_node_id FROM t_telematics ORDER BY '
                 'journey_node_id DESC LIMIT 1')
    logger.info('reading formatted routing data from t_telematics table')
    node_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        node_id = cur.fetchall()[0][0]
    except sqlalchemy.exc.OperationalError as err:
        logger.info('node info read unsuccessful')
        raise err
    except ValueError as err:
        logger.info('node infos read unsuccessful')
        raise err
    except IndexError:
        logger.info('No node ID in t_telematics')
    return node_id


def get_sites(client, connection, cur):
    """Gets all vehicles from a client, with the FPS ID and the client ID
    """
    try:
        sql_query = f"SELECT site_id FROM t_sites WHERE client_id={client}"
        cur.execute(sql_query)
        connection.commit()
        sites_fetch = cur.fetchall()
        sites = [site[0] for site in sites_fetch]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching Site IDs")
        raise error
    return sites


def get_fps_vehicle(client, connection, cur):
    """Gets all sites from a client
    """
    try:
        sql_query = ("SELECT vehicle_id, client_vehicle_id FROM t_vehicles "
                     f"WHERE client_id={client}")
        cur.execute(sql_query)
        connection.commit()
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching vehicle IDs")
        raise error
    vehicle_id_db = cur.fetchall()
    vehicle_dict = {vehicle[1]: vehicle[0] for vehicle in vehicle_id_db}
    return vehicle_dict


def get_fps_yardtrip_id(connection, cur):
    '''Return the largest currently assigned fps yard trip id'''
    # establish FPS database connection
    query_str = ('SELECT yard_trip_id FROM t_yard_trips ORDER BY '
                 'yard_trip_id DESC LIMIT 1')
    logger.info('reading latest yard trip ID')
    trip_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        trip_id = cur.fetchall()[0][0]
    except sqlalchemy.exc.OperationalError as err:
        logger.info('Yard trip ID fetch unsuccessful')
        raise err
    except ValueError as err:
        logger.info('Yard trip ID fetch unsuccessful')
        raise err
    except IndexError:
        logger.info('No trip ID in t_yard_trips')
    return trip_id


def get_fps_vehicle_id(connection, cur):
    '''Return the largest currently assigned fps vehicle id'''
    # establish FPS database connection
    query_str = (
        'SELECT vehicle_id FROM t_vehicles ORDER BY vehicle_ID DESC LIMIT 1')
    logger.info(
        'reading formatted routing data from t_telematics table')
    vehicle_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        vehicle_id = cur.fetchall()[0][0]
    except sqlalchemy.exc.OperationalError as err:
        logger.info('vehicle ID info read unsuccessful')
        raise err
    except ValueError as err:
        logger.info('Vehicle ID infos read unsuccessful')
        raise err
    except IndexError:
        logger.info('No Vehicle ID in t_vehicles')
    return vehicle_id


def add_missing_vehicle_id(ids, client_id, connection, cur):
    """Adds a list of fleet IDs to the vehicle database

    Args:
        ids (list): list of fleet IDs missing from database
        client_id (int): Unique client ID
        connection (_type_): _description_
        cur (_type_): _description_
    """
    cnx = dbh.create_alch_engine()
    start_id = get_fps_vehicle_id(connection, cur) + 1
    df = pd.DataFrame(data=ids, columns=['client_vehicle_id'])
    df['site_id'] = 1
    df['vehicle_id'] = df.index + start_id
    df['tru_id'] = 1
    df['spec_id'] = 1
    df['registration'] = ""
    df['client_id'] = client_id
    df.to_sql('t_vehicles', con=cnx, if_exists='append', index=False)
    cnx.dispose()
    logger.debug(f"New vehicles added to the database from {start_id} to "
                 f"{df['vehicle_id'].max()}")
    return


def asign_vehicle_id(ids, client_id, connection, cur):
    """Returns the FPS vehicle IDs for each client fleet id

    Args:
        ids (Series): list of fleet IDs
        client_id (int): unique client ID

    Returns:
        Series: FPS vehicle IDs
    """
    vehicle_dict = get_fps_vehicle(client_id, connection, cur)
    new_ids = ids.map(vehicle_dict)
    # If there are Vehicle IDs not in the database, it will add them
    mask_bad = new_ids.isna()
    missing_fleet_ids = ids[mask_bad].unique()
    if len(missing_fleet_ids) > 0:
        add_missing_vehicle_id(missing_fleet_ids, client_id, connection, cur)
    # Remap the FPS vehicle IDs with the new aditions
    vehicle_dict = get_fps_vehicle(client_id, connection, cur)
    new_ids = ids.map(vehicle_dict)
    return new_ids


def order_items(items, table, index_col, criteria_column, connection, cur):
    try:
        sql_query = f"""SELECT {index_col}
            FROM {table} WHERE {index_col} IN {tuple(items)}
            ORDER BY {criteria_column}"""
        cur.execute(sql_query)
        connection.commit()
        items_fetch = cur.fetchall()
        items_ordered = [i[0] for i in items_fetch]
    except (Exception, psycopg2.Error) as error:
        logger.error(f"Error while ordering {index_col}")
        raise error
    return items_ordered
