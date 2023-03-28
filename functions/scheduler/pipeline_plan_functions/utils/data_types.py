# Adjust data types

import pandas as pd
import json
from python_utils.utils.logger import logger


def valid_datetime(timestamp):
    newtime = False
    try:
        newtime = pd.to_datetime(timestamp)
    except Exception:
        logger.info(f"Not valid timestamp")
    finally:
        return newtime


def get_hours(dtseries):
    return (dtseries - pd.to_datetime(dtseries.dt.date)).dt.total_seconds()/3600


def separate_chargers(chargers):
    charger1 = 22
    charger2 = 50
    try:
        chargers = json.loads(chargers)
        charger2 = chargers[-1]
        if len(chargers)>0:
            charger1 = chargers[0]
        else:
            charger1 = 0
    except Exception as e:
        logger.error(e)
        raise(e)
    return charger1, charger2


def list_to_string(python_list):
    if len(python_list) == 1:
        new_list = f"({python_list[0]})"
    else:
        new_list = str(tuple(python_list))
    return new_list
