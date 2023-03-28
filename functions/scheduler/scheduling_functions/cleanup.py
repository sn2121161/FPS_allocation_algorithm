from python_utils.utils.logger import logger
import pandas as pd
import psycopg2
import numpy as np

TIME_FRACT = 0.5

# Bill adding one parameter
def export_charge_schedule(output, output_soc, settings, vehicles, times, cnx):
    """Creates a profile from the scheduler and upload to the database

    Args:
        output (array): output from optimiser, energy output (in kWh) per
                HH per vehicle
        settings (dict): user settings and global variables
        vehicles (list): list of vehicle IDs
        times (array): list of time intervals
        cnx: sqalchemy connection engine
    """
    scenario_id = settings['scenario_id']
    # Create table of the charging outputs (kWh) per time period per vehicle.
    charge_outputs = pd.DataFrame(data=output)
    charge_outputs['datetime'] = times
    charge_outputs.set_index('datetime', inplace=True)
    charge_outputs.columns = vehicles
    # Convert the energy to power (kW)
    schedule = (charge_outputs.stack() / TIME_FRACT
                ).to_frame(name='power_demand_kw')
    schedule['scenario_id'] = scenario_id
    schedule.reset_index(inplace=True)
    schedule.rename(columns={'level_1': 'allocated_vehicle_id'}, inplace=True)
    # Bill adding 
    soc_outputs = pd.DataFrame(data=output_soc)
    soc_outputs['datetime'] = times
    soc_outputs.set_index('datetime', inplace=True)
    soc_outputs.columns = vehicles
    schedule_soc = (soc_outputs.stack()
                ).to_frame(name='vehicle_soc')
    schedule_soc['scenario_id'] = scenario_id
    schedule_soc.reset_index(inplace=True)
    schedule_soc.rename(columns={'level_1': 'allocated_vehicle_id'}, inplace=True)
    schedule = schedule.merge(schedule_soc,on=['datetime','allocated_vehicle_id','scenario_id'],how='left')
    postgreSQLTable = "t_charge_demand"
    try:
        schedule.to_sql(postgreSQLTable, con=cnx, if_exists='append',
                        index=False)
        logger.debug(f"Updated schedule for scenario {scenario_id} "
                     "in t_charge_demand")
    except Exception as e:
        logger.error(f"Unable to export schedule for scenario {scenario_id}")
        logger.exception(e)
    return


def calculate_breaches(output, capacity):
    """Calculate periods where the energy demand breaches site capacity

    Args:
        output (2d array): kWh used per time period
        capacity (1d array): available site capacity (in kW)

    Returns:
        int: number of site breaches
    """
    breach_vector = ((capacity * TIME_FRACT - output.sum(axis=1))
                     < -0.01).astype(int)
    # Bill
    if breach_vector.sum() > 0:
        print(breach_vector)
    return breach_vector.sum()


def excess_capacity_cost(output, capacity, distribution, connection, cur):
    """Calculate the electricity excess capacity costs"""
    if distribution == -1:
        return 0
    # How many kWh go over the available site capacity
    excess_kwh = np.clip(output.sum(axis=1) - capacity * TIME_FRACT,
                         a_min=0, a_max=None).sum()
    # Get excess capacity charge £/kVA/day
    sql_query = (
        f"""SELECT exceeded_capacity_charge FROM t_electricity_price
        WHERE distribution_id={distribution}""")
    cur.execute(sql_query)
    connection.commit()
    charge_kva = cur.fetchall()[0][0]
    # Get power factor
    sql_query = (
        """SELECT parameter_value FROM t_system_parameters
        WHERE parameter_name='power_factor' LIMIT 1""")
    cur.execute(sql_query)
    connection.commit()
    power = float(cur.fetchall()[0][0])
    return (excess_kwh / power) * charge_kva


# Bill adding two parameters
def update_scenarios(breaches, nbreach, nmagic, ntimeout, kwh, excess, 
                     scenario, min_soc, max_soc, connection, cur):
    """Update the charging scenario row summary data"""
    update_dict = {
        'asc_breaches': breaches,
        'breach_days': nbreach,
        'unfeasible_days': nmagic,
        'timeout_days': ntimeout,
        'output_kwh': kwh,
        'schedule_status': "'c'",
        'excess_capacity_cost': excess,
        # Bill adding
        'min_soc': min_soc,
        'max_soc': max_soc
    }
    column_string = ", ".join([f"{c}={update_dict[c]}"
                               for c in update_dict.keys()])
    try:
        sql_query = f"""UPDATE t_charging_scenarios
            SET {column_string}
            WHERE scenario_id={scenario};"""
        cur.execute(sql_query)
        connection.commit()
        logger.debug("Updated t_charging_scenarios with QA")
    except (Exception, psycopg2.Error) as error:
        logger.error("Error updating t_charging_scnearios")
        raise error
    return
