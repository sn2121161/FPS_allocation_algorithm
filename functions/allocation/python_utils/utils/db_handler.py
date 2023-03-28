import os
import sys

import pandas as pd
import psycopg2
import sqlalchemy

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CDIR)
from logger import logger


class DbHandler():

    def __init__(self,
                 username: str,
                 password: str,
                 database: str,
                 host: str,
                 port: str,
                 do_connect_db: bool = True):
        '''
        username: str
        password: str
        database: str
        host: str
        port: str
        do_connect_db: connect DB during the construction. default True
        '''
        self._username = username
        self._password = password
        self._database = database
        self._host = host
        self._port = port

        logger.info('DB name: %s' % self._database)
        # --- DB connection
        self._db_connect_args = {
            'user': self._username,
            'password': self._password,
            'database': self._database,
            'host': self._host,
            'port': self._port,
            'sslmode': 'require',
        }
        self._sa_engine_url = sqlalchemy.engine.URL.create(
            drivername='postgresql+psycopg2',
            username=self._username,
            password=self._password,
            database=self._database,
            host=self._host,
            port=self._port,
            query={'sslmode': 'require'},
        )
        self._psycopg_conn = None
        self._sa_engine = None

        if do_connect_db:
            self.prepare_db()

    def __del__(self):
        self.reset_db()

    def prepare_db(self):
        self._prepare_alchemy_engine()
        self._prepare_psycopg_connect()

    def reset_db(self):
        if self._psycopg_conn is not None:
            self._psycopg_conn.close()
            self._psycopg_conn = None
            logger.info("psycong2 connection closed")
        if self._sa_engine is not None:
            self._sa_engine = None
            logger.info("sqlalchemy connection closed")

    def _prepare_psycopg_connect(self):
        if self._psycopg_conn is not None:
            logger.info('Connection is not None')
            return
        logger.info('Connecting DB %s' % self._database)
        try:
            self._psycopg_conn = psycopg2.connect(**self._db_connect_args)
        except psycopg2.OperationalError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        logger.info('Connected DB %s' % self._database)

    def _prepare_alchemy_engine(self):
        if self._sa_engine is not None:
            logger.info('alchemy engine is not None')
            return
        logger.info('Preparing alchemy engine %s ' % self._database)
        try:
            self._sa_engine = sqlalchemy.create_engine(self._sa_engine_url)
        except sqlalchemy.exc.ArgumentError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        logger.info('Prepared alchemy engine %s' % self._database)

    @staticmethod
    def _column_names_str(column_names: list):
        if column_names is None:
            clm_names_str = '*'
        elif len(column_names) == 0:
            clm_names_str = '*'
        elif column_names[0] == '*':
            clm_names_str = column_names[0]
        else:
            clm_names_str = ','.join(['\"%s\"' % x for x in column_names])
        return clm_names_str

    def _column_names_check(self, table_name: str, df: pd.DataFrame):
        db_clm_names = self.all_column_names(table_name)
        df_clm_names = df.columns.values
        not_exist = [x not in db_clm_names for x in df_clm_names]
        if any(not_exist):
            clms_not_exist = ','.join(df_clm_names[not_exist])
            err_str = '%s not exist in %s' % (clms_not_exist, table_name)
            logger.critical(err_str)
            raise ValueError(err_str)

    def _insert_into_sql_cmd(self, table_name: str, data_dic: dict):
        '''
        SQL insert command
        '''
        attrs = ','.join([k for k in data_dic.keys()])
        vals = ','.join([
            '\'%s\'' % str(v) if isinstance(v, str) else str(v)
            for v in data_dic.values()
        ])
        cmd = ' '.join([
            'INSERT INTO',
            table_name,
            '(%s)' % attrs,
            'VALUES',
            '(%s)' % vals,
        ])
        try:
            with self._psycopg_conn.cursor() as cur:
                cur.execute(cmd)
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        self._psycopg_conn.commit()

    def _select_cmd(self, table_name: str, column_names: list, condition: str,
                    order: str) -> str:
        clm_names_str = self._column_names_str(column_names)
        cmd_list = ['SELECT', clm_names_str, 'FROM', table_name]
        if condition != '':
            cmd_list.extend(['where', condition])
        if order != '':
            cmd_list.append(order)
        cmd = ' '.join(cmd_list)
        logger.debug('Fetching columns: %s' % clm_names_str)
        logger.debug('command: %s' % cmd)
        return cmd

    def select(self,
               table_name: str,
               column_names: list,
               condition: str = '',
               order: str = '') -> list:
        '''
        '''
        cmd = self._select_cmd(table_name, column_names, condition, order)
        try:
            with self._psycopg_conn.cursor() as cur:
                cur.execute(cmd)
                rows = cur.fetchall()
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            rows = None
        return rows

    def df_read_sql_query(self,
                          table_name: str,
                          column_names: list,
                          condition: str = '') -> pd.DataFrame:
        '''
        table_name: str
        column_names: list of string,
                      if [] or [''], all columns('*') are selected
        condition: str
        '''
        cmd = self._select_cmd(table_name, column_names, condition, '')
        df = pd.read_sql_query(cmd, con=self._sa_engine)
        return df

    def all_column_names(self, table_name: str) -> list:
        """
        Return column names of the table

        @Args
        table_name: str
        @Returns
        clm_names: list of str
        """
        cmd_list = [
            'select COLUMN_NAME',
            'from information_schema.columns',
            'where table_name=\'%s\'' % table_name,
        ]
        cmd = ' '.join(cmd_list)
        with self._psycopg_conn.cursor() as cur:
            try:
                cur.execute(cmd)
            except Exception as err:
                logger.error('%s %s %s' % (self._database, cmd, err))
                raise err
            clm_names = [x[0] for x in cur]
        return clm_names

    def unique_values(self, t_name: str, c_name: str, condition: str = ''):
        '''
        t_name: table name
        c_name: column name
        condition: condition
        '''
        cmd_list = [
            'SELECT DISTINCT(%s)' % c_name,
            'FROM %s' % t_name,
        ]
        if condition != '':
            cmd_list.append(condition)
        cmd = ' '.join(cmd_list)
        with self._psycopg_conn.cursor() as cur:
            try:
                cur.execute(cmd)
                rows = cur.fetchall()
            except Exception as err:
                logger.error('%s %s' % (self._database, err))
                raise err
        try:
            dst = [x[0] for x in rows]
        except IndexError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        return dst

    def highest_value(self, t_name: str, c_name: str, condition: str = ''):
        '''
        t_name: table name
        c_name: column name
        condition: condition
        '''
        cmd_list = [
            'SELECT MAX(%s)' % c_name,
            'FROM %s' % t_name,
        ]
        # cmd_list = [
        #     'SELECT %s' % c_name,
        #     'FROM %s' % t_name,
        #     'order by %s asc limit 1' % c_name,
        # ]
        if condition != '':
            cmd_list.append(condition)
        cmd = ' '.join(cmd_list)
        try:
            with self._psycopg_conn.cursor() as cur:
                cur.execute(cmd)
                rows = cur.fetchall()
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        try:
            tmp = rows[0]
        except IndexError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        try:
            dst = tmp[0]
        except IndexError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        return dst

    def lowest_value(self, t_name: str, c_name: str, condition: str = ''):
        '''
        t_name: table name
        c_name: column name
        condition: condition
        '''
        cmd_list = [
            'SELECT MIN(%s)' % c_name,
            'FROM %s' % t_name,
        ]
        # cmd_list = [
        #     'SELECT %s' % c_name,
        #     'FROM %s' % t_name,
        #     'order by %s desc limit 1' % c_name,
        # ]
        if condition != '':
            cmd_list.append(condition)

        cmd = ' '.join(cmd_list)
        try:
            with self._psycopg_conn.cursor() as cur:
                cur.execute(cmd)
                rows = cur.fetchall()
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        try:
            tmp = rows[0]
        except IndexError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        try:
            dst = tmp[0]
        except IndexError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        return dst

    def _to_sql_by_df_from_dic(self, data_dic: dict):
        logger.debug('Converting dict to DataFrame')
        try:
            df = pd.DataFrame(data_dic)
        except ValueError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        logger.debug('Converting dict to DataFrame done')
        return df

    def df_to_sql(self, table_name: str, df: pd.DataFrame, **args: int):
        '''
        Args
        table_name: str,  table name
        df: pd.DataFrame, data

        if_exists: {‘fail’, ‘replace’, ‘append’}, default ‘append’
        '''
        if_exists = args.get('if_exists', 'append')
        try:
            logger.info('Inserting data into %s' % table_name)
            df.to_sql(
                table_name,
                con=self._sa_engine,
                if_exists=if_exists,
                index=False,
                # method=None,
            )
            logger.info('Inserted data into %s' % table_name)
        except sqlalchemy.exc.ProgrammingError as err:
            logger.error('%s %s' % (self._database, err))
            raise err
        except Exception as err:
            logger.error('%s %s' % (self._database, err))
            raise err

    def insert_into(self, table_name: str, data: list, **args: int):
        '''
        data: dict {attribute name: [value], ...}
        '''
        df = self._to_sql_by_df_from_dic(data)
        self.df_to_sql(table_name, df, **args)

    def date_condition_str(self, cname: str, bgn_date: str, end_date: str):
        '''
        cname: str, column name of datetime for the condition
        bgn_date: str, %Y-%m-%d %H:%M:%S, start datetime
        end_date: str, %Y-%m-%d %H:%M:%S, end datetime
        '''
        date_condition = ' '.join([
            '%s BETWEEN' % cname,
            '\'%s\' AND \'%s\'' % (bgn_date, end_date),
        ])
        return date_condition


if __name__ == '__main__':
    username = os.getenv('pipe_db_user')
    password = os.getenv('pipe_db_pswd')
    database = os.getenv('pipe_db_name')
    host = os.getenv('pipe_db_host')
    port = os.getenv('pipe_db_port')
    do_connect_db = True
    dbh = DbHandler(username, password, database, host, port, do_connect_db)
    print(dbh.lowest_value('stg_masternaut_raw', 'processed_datetime'))
    print(dbh.highest_value('stg_masternaut_raw', 'processed_datetime'))
