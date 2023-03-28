import pandas as pd
import os
import psycopg2
import sqlalchemy
import datetime as dt
import json
import pipeline_plan_functions.utils.pipe_db_handler as dbh
import pipeline_plan_functions.utils.data_handler as dh
from python_utils.utils.logger import logger
logger.setLevel(os.getenv('log_level', "DEBUG"))


def get_allocations_tocharge(run, connection, cur):
    """Gets all allocation IDs resulting from a run
    """
    try:
        sql_query = f"""SELECT allocation_id FROM t_allocation
            WHERE run_id={run} AND schedule_charge=2"""
        cur.execute(sql_query)
        connection.commit()
        allocations_fetch = cur.fetchall()
        allocation_ids = [site[0] for site in allocations_fetch]
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching Allocation IDs")
        raise error
    return allocation_ids


def get_fps_scenario_id(connection, cur):
    '''Return the largest currently assigned fps allocation id'''
    query_str = (
        """SELECT scenario_id FROM t_charging_scenarios
        ORDER BY scenario_id DESC LIMIT 1""")
    logger.debug('reading last allocation ID')
    scenario_id = 1
    try:
        cur.execute(query_str)
        connection.commit()
        scenario_id = cur.fetchall()[0][0]
    except sqlalchemy.exc.OperationalError as err:
        logger.info('scenario ID read unsuccessful')
        raise err
    except ValueError as err:
        logger.info('scenario ID read unsuccessful')
        raise err
    except IndexError:
        logger.info('No scenario ID in t_charging_scenarios')
    return scenario_id


def create_scheduling_table(inputs, connection, cur):
    """Takes the scheduling inputs and creates a scenario table

    The scenario table has a row for each scenario ID. Each scenario ID is
    associated with an allocation ID (collection of routes), but there can be
    multiple scenario IDs with the same allocation ID.
    """
    if inputs['allocation_ids'] is None:
        # If you don't setup any allocation IDs, it will look at the
        # allocations with the same run_id
        run = inputs['run_id']
        allocation_ids = get_allocations_tocharge(run, connection, cur)
    else:
        allocation_ids = json.loads(inputs['allocation_ids'])
    scenario_cols = ['scenario_id', 'run_id', 'smart_charging',
                     'schedule_status']
    # Finds the charging modes (BAU/opt/both)
    # Bill
    if inputs['charging_mode'] is None:
        charging_modes = ['BAU', 'opt']
    else:
        charging_modes = json.loads(inputs['charging_mode'])
    # Creates a row for each allocation_id and each charging mode
    idx = pd.MultiIndex.from_product([allocation_ids, charging_modes],
                                     names=['allocation_id', 'charging_mode'])
    df = pd.DataFrame(index=idx, columns=scenario_cols).reset_index()
    largest_scenario_id = get_fps_scenario_id(connection, cur)
    df['scenario_id'] = df.index + largest_scenario_id + 1
    df['schedule_status'] = 'n'
    df['run_id'] = inputs['run_id']
    df['smart_charging'] = True
    df.loc[df['charging_mode'] == 'BAU', 'smart_charging'] = False
    df.drop(columns=['charging_mode'], inplace=True)
    return df


def list_to_string(python_list):
    """Converts a python list/array into a list suitble for sql query"""
    if len(python_list) == 1:
        new_list = f"({python_list[0]})"
    else:
        new_list = str(tuple(python_list))
    return new_list


def get_chargers_from_allocation(allocation_ids, connection, cur):
    """Gets charging data from the allocations
    """
    try:
        sql_query = f"""SELECT allocation_id, charger1, charger2,
            num_charger1, num_charger2 FROM t_allocation
            WHERE allocation_id IN {list_to_string(allocation_ids)}"""
        cur.execute(sql_query)
        connection.commit()
        allocations_data = cur.fetchall()
        # Charger 1 is the slow one (AC) and charger 2 is fast (DC)
        allocation_dict = {
            'charger1': {row[0]: row[1] for row in allocations_data},
            'charger2': {row[0]: row[2] for row in allocations_data},
            'num_charger1': {row[0]: row[3] for row in allocations_data},
            'num_charger2': {row[0]: row[4] for row in allocations_data}}
    except (Exception, psycopg2.Error) as error:
        logger.error("Error while fetching charger data")
        raise error
    return allocation_dict


def add_charging_data(df, connection, cur):
    """Adds charging data to each scenario.
    """
    charger_data = get_chargers_from_allocation(df['allocation_id'].unique(),
                                                connection, cur)
    new_df = df.copy()
    for c in ['charger1', 'charger2', 'num_charger1', 'num_charger2']:
        new_df[c] = new_df['allocation_id'].map(charger_data[c])
    # Identifies if there's a single charger (homogeneous) or a mix
    homogeneous_charger = (new_df[['num_charger1', 'num_charger2']] == 0
                           ).any(axis=1)
    charger_mix_dict = {True: 'uniform', False: 'mixed'}
    new_df['charger_type'] = homogeneous_charger.map(charger_mix_dict)
    return new_df


def new_rows_charging(df):
    """Adds new scenarios with a uniform charger, not currently used"""
    new_rows = []
    largest_scenario_id = df['scenario_id'].max()
    for idx in df.index:
        if df.loc[idx, 'charger_type'] == 'mixed':
            new_row = df.loc[idx].copy()
            slow_number = new_row['num_charger1']
            new_row['num_charger1'] = 0
            new_row['num_charger2'] += slow_number
            new_row['charger_type'] = 'uniform'
            largest_scenario_id += 1
            new_row['scenario_id'] = largest_scenario_id
            new_rows.append(new_row)
    # new_df = pd.concat(new_rows, axis=1).transpose()
    new_df = pd.DataFrame(new_rows)
    return new_df


def main():
    logger.debug(f"Started schedulling app at {dt.datetime.now()}")
    try:
        connection, cur = dbh.database_connection('test')
        # FIND THE MOST UP TO DATE RUN ID
        run = dh.get_current_run(connection, cur)
        # Get run input parameters
        inputs = dh.get_inputs('t_run_charging', run, connection, cur)
        df = create_scheduling_table(inputs, connection, cur)
        df = add_charging_data(df, connection, cur)
        dbh.upload_table(df, 't_charging_scenarios')
    except Exception as e:
        logger.error(e)
        SystemExit(e)
    finally:
        cur.close()
        connection.close()
        logger.info("Closed db connection")
    return df['scenario_id'].values


if __name__ == '__main__':
    main()
