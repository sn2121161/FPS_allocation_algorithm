import numpy as np
from python_utils.utils.logger import logger
import cvxpy as cp

logger.setLevel('DEBUG')
# from cvxopt.modeling import variable, op, max, sum

TIME_FRACT = 0.5
CHARGER_EFF = 0.9  # FIXME put this in the database
BATTERY_FACTOR = 0
ASC_XUSE = 0.9


def linear_optimiser_V10(matrices, day_vectors, vehicle_vectors, params,
                         final_soc, opt_level, evout_arr, final_soc_arr_h,
                         weight_time=0.01, battery_factor=BATTERY_FACTOR):
    """Linear optimisation for a single day charging, mixed fleet

    This optimiser uses CVXPY to find optimal power outputs over a day.
    Uses 2 different charger powers, and a varying site capacity.
    Objective: reduce overall electricity spend and maximise the charge
    delivered.
    If this is unfeasible, it will move to the next optimisation level:
        breaching site capacity

    Args:
        weight_time (float): weight given to charging early
        battery_factor (float): extra battery allowance to fully recharge the
            battery when the rate drops (above ~80%)

    Returns:
        final_soc (1D array): end of day final SOC for each vehicle
        opt_level (str): the level of optimisation that was feasible
        evout (2D array): Outputs (kWh) for each time period per vehicle

    """
    # Bill
    soc_margin = params['soc_margin']
    prices = day_vectors[0]
    rel_vector = vehicle_vectors[0]
    battery_cap = vehicle_vectors[2]
    charger1 = min(vehicle_vectors[4].min(), params['charger1'])
    charger2 = min(vehicle_vectors[5].min(), params['charger2'])
    sessionM = matrices[2]
    charger_efficiency = matrices[3]
    ev_use = matrices[1]
    availableM = matrices[0]
    cumul_matrix = np.cumsum(ev_use, axis=0)
    # Number of vehicles
    N = availableM.shape[1]
    # Number of time periods
    T = availableM.shape[0]

    # Define output variable
    outputs = cp.Variable((T, N), nonneg=True)
    # battery = cp.Variable(T)
    chargerM2 = cp.Variable((T, N), boolean=True)

    constraints = []

    if T > 1:
        # Doesn't go over 100%+ SOC or below 0% (eq. 4-5)
        constraints.append(
            cp.cumsum(charger_efficiency @ outputs, axis=0) + cumul_matrix
            + np.reshape(rel_vector, (1, -1))
            # <= cp.Constant(0.00001))
            <= battery_factor*np.reshape(battery_cap, (1, -1)))
        constraints.append(
            cp.cumsum(charger_efficiency @ outputs, axis=0) + cumul_matrix
            + np.reshape(rel_vector, (1, -1))
            + np.reshape(battery_cap, (1, -1))
            >= cp.Constant(0))

    # Limits the number of fast chargers (eq. 6)
    constraints.append(cp.sum(chargerM2, axis=1) <= params['num_charger2'])
    # Limits the charge rate for each vehicle, time (eq. 7)
    constraints.append(outputs/TIME_FRACT
                       <= availableM * charger1
                       + chargerM2 * (charger2-charger1))
    # Limits the number of chargers depending on availability (eq. 9)
    constraints.append(chargerM2 <= availableM)
    # Same charger for each session (eq. 10)
    for s in sessionM:
        i = s[1]
        while i+1 < s[2]:
            constraints.append(chargerM2[i, s[0]] == chargerM2[i+1, s[0]])
            i += 1
    # limits the overall site capacity (eq. 2)
    constraints.append(
        (cp.sum(outputs, axis=1) <= day_vectors[1] * TIME_FRACT))

    T = len(prices)
    timepricing = [i*weight_time for i in range(T)]
    objective = cp.Minimize(  # eq 2
        cp.sum(prices @ outputs)  # total electricity costs
        - 100000*cp.sum(outputs)  # maximises charging
        + cp.sum(timepricing @ outputs)  # encourages charging earlier
        )
    problem = cp.Problem(objective, constraints)

    # Solve and print to the screen
    problem.solve(solver=cp.GLPK_MI)  # 'CBC', GLPK_MI

    # If unfeasible, tries to charge to next day
    if problem.status in ["infeasible", "unbounded"]:
        logger.warning("=================BREACH========================")
        opt_level.value, evout = linear_optimiser_breach(
            matrices, day_vectors, vehicle_vectors, params)
    else:
        logger.info('Optimisation succesfully run in normal mode')
        # opt_level = 'main'
        opt_level.value = 0
        evout = outputs.value
        # chout = chargerM2.value
        # bout = 0  # battery.value

    # Generate a final SoC array
    rel_vector = vehicle_vectors[0] 
    ev_use = matrices[1]
    charger_efficiency = matrices[3]    
    final_soc[:] = (rel_vector + (
        (charger_efficiency @ evout).sum(axis=0)
        + ev_use.sum(axis=0))).round(6)
    
    evout_arr[:] = evout.reshape(-1)
    # returned_values = [final_soc, opt_level, evout_arr]
    # Bill
    soc_matrix = np.zeros((T,N))
    soc_matrix[0] = [100] * N
    for r in range (1, T):
        for c in range(N):
            soc_matrix[r,c] = soc_matrix[r-1,c] + (charger_efficiency @ evout)[r,c] + ev_use[r,c] 
    final_soc_arr_h[:] = soc_matrix.reshape(-1)
    returned_values = [final_soc, opt_level, evout_arr,final_soc_arr_h]
    return returned_values


def linear_optimiser_breach(matrices, day_vectors, vehicle_vectors, params,
                            weight_time=0.01,
                            battery_factor=BATTERY_FACTOR):
    """Linear opt for EV charging with capacity breaches

    This optimiser uses CVXPY to find optimal power outputs over a day.
    Uses 2 different charger powers, and a varying site capacity.
    Objective: reduce overall electricity spend, maximise energy delivered,
        reduce number of breaches.
    If this is unfeasible, it will go to a catch-all 'magic charging' case

    Args:
        inputs (list): daily matrices or vectors for prices,
            ev energy use, availability, site capacity, times, charging
            sessions and charger efficiency.
        inp (dict): dictionary of user inputs and settings
        vectors (list): list of arrays corresponding, for each vehicle to the
            initial missing charge, next day's required energy, the battery
            capacity, the time periods, vehicle IDs and the max charge rate.
        cost_fullcharge (float): weight given to prioritising a full charge
            each night
        weight_time (float): weight given to charging early

    Returns:
        opt_level (str): the level of optimisation that was feasible
        evout (2D array): Outputs (kWh) for each time period per vehicle
    """
    rel_vector = vehicle_vectors[0]
    next_req = vehicle_vectors[1]
    battery_cap = vehicle_vectors[2]
    # vehchargerate = vectors[4]
    charger1 = min(vehicle_vectors[4].min(), params['charger1'])
    charger2 = min(vehicle_vectors[5].min(), params['charger2'])
    charger_efficiency = matrices[3]
    sessionM = matrices[2]
    prices = day_vectors[0]
    capacity_vector = day_vectors[1]
    extraCap = params['asc_kw']*params['asc_margin']
    ev_use = matrices[1]
    availableM = matrices[0]
    cumul_matrix = np.cumsum(ev_use, axis=0)
    N = availableM.shape[1]
    T = availableM.shape[0]
    timepricing = [i*weight_time for i in range(T)]
    # Define output variable
    outputs = cp.Variable((T, N), nonneg=True)
    # battery = cp.Variable(T)
    chargerM2 = cp.Variable((T, N), boolean=True)
    timebreaches = cp.Variable(T, boolean=True)

    constraints = []
    # print('test7')
    # limits the overall site capacity (eq. 17)
    constraints.append(
        cp.sum(outputs, axis=1)  # + battery
        <= capacity_vector * TIME_FRACT
        + timebreaches * TIME_FRACT * extraCap)

    # Charge EV batteries enough each night (eq. 3)
    constraints.append(
        cp.sum(charger_efficiency @ outputs, axis=0)
        + ev_use.sum(axis=0) + rel_vector
        + battery_cap >= (-1) * next_req)
    if T > 1:
        # Doesn't go over 100%+ SOC or below 0% (eq. 4-5)
        constraints.append(
            cp.cumsum(charger_efficiency @ outputs, axis=0) + cumul_matrix
            + np.reshape(rel_vector, (1, -1))
            # <= cp.Constant(0.00001))
            <= battery_factor*np.reshape(battery_cap, (1, -1)))
        constraints.append(
            cp.cumsum(charger_efficiency @ outputs, axis=0) + cumul_matrix
            + np.reshape(rel_vector, (1, -1))
            + np.reshape(battery_cap, (1, -1))
            >= cp.Constant(0))

    # Limits the number of fast chargers (eq. 6)
    constraints.append(cp.sum(chargerM2, axis=1) <= params['num_charger2'])
    # Limits the charge rate for each vehicle, time (eq. 7)
    constraints.append(outputs/TIME_FRACT
                       <= availableM * charger1
                       + chargerM2 * (charger2-charger1))
    # Limits the number of chargers depending on availability (eq. 9)
    constraints.append(chargerM2 <= availableM)
    # Same charger for each session (eq. 10)
    for s in sessionM:
        i = s[1]
        while i+1 < s[2]:
            constraints.append(chargerM2[i, s[0]] == chargerM2[i+1, s[0]])
            i += 1

    objective = cp.Minimize(  # eq.16
        cp.sum(prices @ outputs)  # Cost of charging EVs
        - 100000*cp.sum(outputs)
        + cp.sum(timepricing @ outputs)  # encourages charging earlier
        )  # Breaching events
    problem = cp.Problem(objective, constraints)

    # Solve and print to the screen
    problem.solve(solver=cp.GLPK_MI)  # 'CBC', GLPK_MI
    logger.info(f"Optimisation status (breach mode): {problem.status}")

    # If unfeasible, tries to charge to next day
    if problem.status in ["infeasible", "unbounded"]:
        logger.warning("=================MAGIC========================")
        opt_level = 2
        evout = magic_charging(matrices, vehicle_vectors)
    else:
        opt_level = 1
        evout = outputs.value
        # print(timebreaches.value)
        # chout = chargerM2.value
        # bout = 0  # battery.value
    return opt_level, evout


def magic_charging(matrices, vehicle_vectors):
    """Special charging profile

    This chargign doesn't account for site capacity, charger power,
    state of charge. It simply deliveres the charge required to go back
    to 100%, at equal power in all available time periods.

    Returns:
        evout (2D array): Outputs (kWh) for each time period per vehicle
    """
    availableM = matrices[0]
    charger_efficiency = matrices[3].diagonal().mean()
    ev_use = matrices[1]
    rel_vector = vehicle_vectors[0]
    required_energy = ev_use.sum(axis=0) + rel_vector
    num_timeperiods = availableM.sum(axis=0)
    req_output = np.divide(required_energy, num_timeperiods)/charger_efficiency
    evout = (-1)*availableM*req_output
    return evout


# ~~~~~~~~~~~~~~~~~~ THESE AREN'T IN USE ~~~~~~~~~~~~~~~~~~~


def normal_constraints(matrices, vehicle_vectors, params,
                       battery_factor=BATTERY_FACTOR):
    rel_vector = vehicle_vectors[0]
    next_req = vehicle_vectors[1]
    battery_cap = vehicle_vectors[2]
    charger1 = min(vehicle_vectors[4].min(), params['charger1'])
    charger2 = min(vehicle_vectors[5].min(), params['charger2'])
    sessionM = matrices[2]
    charger_efficiency = matrices[3]
    ev_use = matrices[1]
    availableM = matrices[0]
    cumul_matrix = np.cumsum(ev_use, axis=0)
    N = availableM.shape[1]
    T = availableM.shape[0]

    # Define output variable
    outputs = cp.Variable((T, N), nonneg=True)
    # battery = cp.Variable(T)
    chargerM2 = cp.Variable((T, N), boolean=True)

    constraints = []

    # Charge EV batteries enough each night (eq. 3)
    constraints.append(
        cp.sum(charger_efficiency @ outputs, axis=0)
        + ev_use.sum(axis=0) + rel_vector
        + battery_cap >= (-1) * next_req)
    if T > 1:
        # Doesn't go over 100%+ SOC or below 0% (eq. 4-5)
        constraints.append(
            cp.cumsum(charger_efficiency @ outputs, axis=0) + cumul_matrix
            + np.reshape(rel_vector, (1, -1))
            # <= cp.Constant(0.00001))
            <= battery_factor*np.reshape(battery_cap, (1, -1)))
        constraints.append(
            cp.cumsum(charger_efficiency @ outputs, axis=0) + cumul_matrix
            + np.reshape(rel_vector, (1, -1))
            + np.reshape(battery_cap, (1, -1))
            >= cp.Constant(0))

    # Limits the number of fast chargers (eq. 6)
    constraints.append(cp.sum(chargerM2, axis=1) <= params['num_charger2'])
    # Limits the charge rate for each vehicle, time (eq. 7)
    constraints.append(outputs/TIME_FRACT
                       <= availableM * charger1
                       + chargerM2 * (charger2-charger1))
    # Limits the number of chargers depending on availability (eq. 9)
    constraints.append(chargerM2 <= availableM)
    # Same charger for each session (eq. 10)
    for s in sessionM:
        i = s[1]
        while i+1 < s[2]:
            constraints.append(chargerM2[i, s[0]] == chargerM2[i+1, s[0]])
            i += 1
    # TODO Add battery storage
    return constraints, outputs, chargerM2


def normal_objective(prices, outputs, weight_time=0.01):
    T = len(prices)
    timepricing = [i*weight_time for i in range(T)]
    objective = cp.Minimize(  # eq 2
        cp.sum(prices @ outputs)
        # + battery @ prices
        - 100000*cp.sum(outputs)  # maximises charging
        + cp.sum(timepricing @ outputs)  # encourages charging earlier
        )
    return objective


def linear_optimiser_V9(matrices, day_vectors, vehicle_vectors, params):
    """Linear optimisation for a single day charging, mixed fleet

    This optimiser uses CVXPY to find optimal power outputs over a day.
    Uses 2 different charger powers, and a varying site capacity.
    Objective: reduce overall electricity spend and maximise the charge deliv.
    If this is unfeasible, it will move to the next optimisation level:
        breaching site capacity

    Args:
        weight_time (float): weight given to charging early
        battery_factor (float): extra battery allowance to fully recharge the
            battery when the rate drops (above ~80%)

    Returns:
        final_soc (1D array): end of day final SOC for each vehicle
        opt_level (str): the level of optimisation that was feasible
        evout (2D array): Outputs (kWh) for each time period per vehicle
        chout (2D array): Fast charger selection per time period, vehicle
        bout (2D array): Outputs of battery (kWh) for each time period

    """
    prices = day_vectors[0]
    constraints, outputs, _ = normal_constraints(matrices, vehicle_vectors,
                                                 params)
    # limits the overall site capacity (eq. 2)
    constraints.append(
        normal_capacity(outputs, day_vectors[1]))

    objective = normal_objective(prices, outputs)
    problem = cp.Problem(objective, constraints)

    # Solve and print to the screen
    problem.solve(solver=cp.GLPK_MI)  # 'CBC', GLPK_MI

    # If unfeasible, tries to charge to next day
    if problem.status in ["infeasible", "unbounded"]:
        logger.warning("=================BREACH========================")
        opt_level, evout = linear_optimiser_breach(
            matrices, day_vectors, vehicle_vectors, params)
    else:
        logger.info('Optimisation succesfully run in normal mode')
        opt_level = 'main'
        evout = outputs.value
        # chout = chargerM2.value
        # bout = 0  # battery.value

    # Generate a final SoC array
    rel_vector = vehicle_vectors[0]
    ev_use = matrices[1]
    charger_efficiency = matrices[3]
    final_soc = (rel_vector + (
        (charger_efficiency @ evout).sum(axis=0)
        + ev_use.sum(axis=0))).round(6)
    return final_soc, opt_level, evout


def normal_capacity(outputs, capacity_vector):
    cons = (cp.sum(outputs, axis=1) <= capacity_vector * TIME_FRACT)
    return cons


def breach_capacity(outputs, timebreaches, params, capacity_vector):
    extraCap = params['asc_kw']*params['asc_margin']
    cons = (cp.sum(outputs, axis=1)  # + battery
            <= capacity_vector * TIME_FRACT
            + timebreaches * TIME_FRACT * extraCap)
    return cons


def breach_objective(prices, outputs, timebreaches, weight_time=0.01):
    T = len(prices)
    timepricing = [i*weight_time for i in range(T)]
    objective = cp.Minimize(  # eq 16
        cp.sum(prices @ outputs)
        + 100000000*cp.sum(timebreaches)
        # + battery @ prices
        - 100000*cp.sum(outputs)  # Total output#
        + cp.sum(timepricing @ outputs)  # encourages charging earlier
        )
    return objective


def linear_optimiser_breach2(matrices, day_vectors, vehicle_vectors, params):
    # FIXME breach scenario not working
    """Linear opt for EV charging with capacity breaches

    This optimiser uses CVXPY to find optimal power outputs over a day.
    Uses 2 different charger powers, and a varying site capacity.
    Objective: reduce overall electricity spend, maximise energy delivered,
        reduce number of breaches.
    If this is unfeasible, it will go to a catch-all 'magic charging' case

    Args:
        inputs (list): daily matrices or vectors for prices,
            ev energy use, availability, site capacity, times, charging
            sessions and charger efficiency.
        inp (dict): dictionary of user inputs and settings
        vectors (list): list of arrays corresponding, for each vehicle to the
            initial missing charge, next day's required energy, the battery
            capacity, the time periods, vehicle IDs and the max charge rate.
        cost_fullcharge (float): weight given to prioritising a full charge
            each night
        weight_time (float): weight given to charging early

    Returns:
        opt_level (str): the level of optimisation that was feasible
        evout (2D array): Outputs (kWh) for each time period per vehicle
        chout (2D array): Fast charger selection per time period, vehicle
        bout (2D array): Outputs of battery (kWh) for each time period
    """
    prices = day_vectors[0]
    constraints, outputs, _ = normal_constraints(
        matrices, vehicle_vectors, params)
    # limits the overall site capacity (eq. 17)
    timebreaches = cp.Variable(len(prices), boolean=True)
    constraints.append(
        breach_capacity(outputs, timebreaches, params, day_vectors[1]))
    objective = breach_objective(prices, outputs, timebreaches)
    # objective = normal_objective(prices, outputs)
    problem = cp.Problem(objective, constraints)
    logger.debug("defined problem")
    # print(problem)
    # Solve and print to the screen
    problem.solve(solver=cp.GLPK_MI)  # 'CBC', GLPK_MI
    logger.info(f"Optimisation status (breach mode): {problem.status}")

    # If unfeasible, tries to charge to next day
    if problem.status in ["infeasible", "unbounded"]:
        logger.warning("=================MAGIC========================")
        opt_level = 'magic'
        evout = magic_charging(matrices, vehicle_vectors)
    else:
        opt_level = 'breach'
        evout = outputs.value
        # chout = chargerM2.value
        # bout = 0  # battery.value
    # opt_level = 'breach'
    # evout = 0
    return opt_level, evout
