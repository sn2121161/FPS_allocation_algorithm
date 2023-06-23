import os
import sys
# import pandas as pd
import psycopg2
import sqlalchemy
from python_utils.utils.logger import logger

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CDIR)


def database_connection(type='test'):
    if type == 'test':
        db_user = os.getenv('pipe_db_user', "")
        db_pswd = os.getenv('pipe_db_pswd', "")
        db_name = os.getenv('pipe_db_name', "")
        db_host = os.getenv('pipe_db_host', "")
        db_port = os.getenv('pipe_db_port', "")

        # local variables
        # db_user = os.getenv('dev_user')
        # db_pswd = os.getenv('dev_pwd')
        # db_name = "Pipeline-DB-New"
        # db_host = os.getenv('dev_host')
        # db_port = 5432

    elif type == 'prod':
        db_user = os.getenv('pipe_prod_user', "")
        db_pswd = os.getenv('pipe_prod_pswd', "")
        db_name = os.getenv('pipe_prod_name', "")
        db_host = os.getenv('pipe_prod_host', "")
        db_port = os.getenv('pipe_prod_port', "")
    db_ssl = os.getenv('psgrsql_ssl_mode', "require")
    try:
        connection = psycopg2.connect(
            user=db_user, password=db_pswd,
            host=db_host,
            port=db_port, database=db_name, sslmode=db_ssl)
        cur = connection.cursor()
    except psycopg2.OperationalError as oe:
        logger.exception(oe)
        raise oe
    return connection, cur


def create_alch_engine():
    db_user = os.getenv('pipe_db_user', "")
    db_pswd = os.getenv('pipe_db_pswd', "")
    db_name = os.getenv('pipe_db_name', "")
    db_host = os.getenv('pipe_db_host', "")
    db_port = os.getenv('pipe_db_port', "")



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
    return cnx


def upload_table(df, table):
    try:
        cnx = create_alch_engine()
        df.to_sql(table, con=cnx, if_exists='append', index=False)
        logger.debug(f"Uploaded to {table}")
    except Exception as e:
        logger.info(f"Error uploading table to {table}")
        raise e
    finally:
        cnx.dispose()
    return


def create_big_engine():
    # Get database credentials
    db_user = os.getenv('newpipe_db_user', "")
    db_pswd = os.getenv('newpipe_db_pswd', "")
    db_name = os.getenv('newpipe_db_name', "")
    db_host = os.getenv('newpipe_db_host', "")
    db_port = os.getenv('newpipe_db_port', "")
    db_conn_str = (
        f'postgresql://{db_user}:{db_pswd}@{db_host}:{db_port}/{db_name}')
    cnx = sqlalchemy.create_engine(db_conn_str)
    return cnx
