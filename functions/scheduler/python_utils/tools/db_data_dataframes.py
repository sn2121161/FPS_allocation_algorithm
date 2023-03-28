import os
import sys
from collections import namedtuple
import numpy as np

CDIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CDIR, '..', '..'))

sys.path.append(ROOT_DIR)
from python_utils.utils.logger import logger
from python_utils.utils.db_handler import DbHandler

DB_ENVS = namedtuple(
    'db_envs',
    'user pswd name host port',
)(
    os.getenv('psgrsql_db_user'),
    os.getenv('psgrsql_db_pswd'),
    os.getenv('psgrsql_db_name'),
    os.getenv('psgrsql_db_host'),
    os.getenv('psgrsql_db_port'),
)


class DbDataDfBase():
    '''
    pd.DataFrame of the table contents in the DB.

    db_df = DbDataDfBase()
    df = db_df.df_from_db(tname, cnames, date_cname,
                          bgn_date, end_date)
    '''

    def __init__(self):
        self._db_h = DbHandler(DB_ENVS.user, DB_ENVS.pswd, DB_ENVS.name,
                               DB_ENVS.host, DB_ENVS.port)

    def df_from_db(self, tname, cnames, date_cname, bgn_date, end_date):
        '''
        return pd.DataFrame that was fetched from the DB

        @Args
        tname: str, table name
        cnames: list, column names
        date_cname: str, date time column name, igore date if value is ''
        bgn_date: str, '%Y-%m-%d %H:%M:%S', start date time
        end_date: str, '%Y-%m-%d %H:%M:%S', end date time

        @Returns
        df: pd.DataFrame
        '''
        if date_cname == '':
            conditions = ''
        else:
            date_condition = self._db_h.date_condition_str(
                date_cname, bgn_date, end_date)
            conditions = date_condition
            if cnames is None:
                cnames = [date_cname]
            if '*' not in cnames and date_cname not in cnames:
                cnames.append(date_cname)
        logger.info('loading %s' % tname)
        df = self._db_h.df_read_sql_query(tname, cnames, conditions)
        logger.info('loaded  %s' % tname)

        if df.shape[0] == 0:
            logger.warning('. '.join([
                'Data from table:%s' % tname,
                'with the condition of %s' % conditions,
                'is empty.',
            ]))
        df = df.fillna(value=np.nan)
        return df


class DbDataDataFrames(DbDataDfBase):
    '''
    Each method returns pd.DataFrame of the table contents in the DB.

    db_df = DbDataDataFrame()
    df = db_df.df_stg_masternaut(bgn_date, end_date, cnames)

    @Args
    bgn_date: str, '%Y-%m-%d %H:%M:%S', start date time
    end_date: str, '%Y-%m-%d %H:%M:%S', end date time
    cnames: list, column names

    @Returns
    df: pd.DataFrame

    '''

    def __init__(self):
        DbDataDfBase.__init__(self)

    def df_t_vehicle(self, cnames=None):
        tname = 't_vehicle'
        date_cname = ''
        bgn_date = None
        end_date = None
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        return df

    def df_stg_masternaut(self, bgn_date, end_date, cnames):
        tname = 'stg_masternaut'
        date_cname = 'processed_datetime'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        df = df.sort_values(date_cname)
        return df

    def df_stg_masternaut_raw(self, bgn_date, end_date, cnames):
        tname = 'stg_masternaut_raw'
        date_cname = 'processed_datetime'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        df = df.sort_values(date_cname)
        return df

    def df_t_route_plan(self, bgn_date, end_date, cnames):
        tname = 't_route_plan'
        date_cname = 'plan_start_date_time'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        df = df.sort_values(date_cname)
        return df

    def df_t_route_node(self, bgn_date, end_date, cnames):
        tname = 't_route_node_sequences'
        date_cname = 'plan_arrival_time'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        df = df.sort_values(date_cname)
        return df

    def df_t_sp_energy_usage(self, bgn_date, end_date, cnames):
        tname = 't_sp_energy_usage'
        date_cname = 'date_time'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        df = df.sort_values(date_cname)
        return df

    def df_t_triad_warning_history(self, bgn_date, end_date, cnames):
        tname = 't_triad_warning_history'
        # date_cname = 'date_time'
        date_cname = 'received_date'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        # df = df.sort_values(date_cname)
        return df

    def df_t_vsm(self, bgn_date, end_date, cnames):
        tname = 't_vsm'
        # date_cname = 'date_time'
        date_cname = ''
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        # df = df.sort_values(date_cname)
        return df

    def df_t_vehicle_energy_estimation(self, bgn_date, end_date):
        tname = 't_vehicle_energy_estimation'
        # date_cname = 'date_time'
        date_cname = ''
        cnames = ['*']
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        return df

    def df_stg_axodel(self, bgn_date, end_date, cnames):
        '''
        bgn_date
        '''
        tname = 'stg_axodel'
        date_cname = 'received'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        return df

    def df_t_weather_forecast_history(self, bgn_date, end_date, cnames=None):
        tname = 't_weather_forecast_history'
        date_cname = 'forecasted_date_time'
        df = self.df_from_db(tname, cnames, date_cname, bgn_date, end_date)
        return df


if __name__ == '__main__':
    db_dfs = DbDataDataFrames()
    bgn_date = '2022-03-08 20:00:00'
    end_date = '2022-03-09 00:00:00'
    cnames = ['*']
    # df = db_dfs.df_stg_axodel(bgn_date, end_date, cnames)
    df = db_dfs.df_t_vehicle()
