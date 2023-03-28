import os
import sys
# import pandas as pd
# import psycopg2
# import sqlalchemy
# from python_utils.utils.logger import logger
from azure.storage.blob import ContainerClient

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CDIR)


def get_container(name):
    key1 = os.getenv('storage_conn_string', "")
    container = ContainerClient.from_connection_string(
        conn_str=key1, container_name=name)
    return container
