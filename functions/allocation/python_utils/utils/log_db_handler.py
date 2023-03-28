import logging
from logging import Handler

import psycopg2


class DbConn():

    def __init__(self, user, pswd, dbname, host, port, options):
        db_connect_args = {
            'user': user,
            'password': pswd,
            'database': dbname,
            'host': host,
            'port': port,
            'sslmode': 'require',
            'options': options,
        }
        # test_Bill 
        print(db_connect_args)
        self._db_conn = None
        try:
            self._db_conn = psycopg2.connect(**db_connect_args)
        except Exception as e:
            raise e
        self._udef_id_val = 'Undefined'

    def __del__(self):
        self.close()

    def close(self):
        if self._db_conn is not None:
            self._db_conn.close()
            self._db_conn = None
        self.db_clm_names = None

    def table_columns(self, table_name):
        cmd = ' '.join(['SELECT * FROM', table_name, 'LIMIT 0'])
        with self._db_conn.cursor() as cur:
            try:
                cur.execute(cmd)
            except Exception as err:
                raise err
            dst = [x[0] for x in cur.description]
        return dst

    def _select_core(self, table_name, clm_names, condition):
        clm_names_str = ','.join(['\"%s\"' % x for x in clm_names])
        cmd = ' '.join([
            'SELECT %s' % clm_names_str,
            'FROM %s' % table_name,
            'where %s' % condition,
        ])
        with self._db_conn.cursor() as cur:
            try:
                cur.execute(cmd)
            except Exception as err:
                raise err
            rows = cur.fetchall()
        return rows

    def select(self, table_name, tar_clm, id_clm, id_val):
        if id_val == '':
            dst = None
        else:
            clm_names = [tar_clm, id_clm]
            condition = '%s = \'%s\'' % (id_clm, id_val)
            rows = self._select_core(table_name, clm_names, condition)
            if len(rows) == 0:
                condition = '%s = \'%s\'' % (id_clm, self._udef_id_val)
                rows = self._select_core(table_name, clm_names, condition)
            dst = rows[0][clm_names.index(tar_clm)]
        return dst

    def insert_into(self, table_name, attrs, vals):
        cmd = ' '.join([
            'INSERT INTO',
            table_name,
            '(%s)' % attrs,
            'VALUES',
            '(%s)' % vals,
        ])
        with self._db_conn.cursor() as cur:
            try:
                cur.execute(cmd)
            except Exception as err:
                raise err
        self._db_conn.commit()


class LogPostgresqlHandler(Handler):

    def __init__(self, db_obj: DbConn, table_name: str, lvl_name: str):
        '''
        db_obj: DbConn class object
        table_name: str
        lvl_name: str, 'CRITICAL', 'ERROR', 'WARNING', 'INFO' or 'DEBUG'
        '''
        self._db_conn = db_obj
        self._table_name = table_name
        self._level_no = getattr(logging, lvl_name)

        self._db_clm_names = self._db_conn.table_columns(self._table_name)

        Handler.__init__(self)

    def emit(self, record):

        def _get_val(rec, key):
            try:
                val_str = '%s' % rec.__dict__[key]
                val_str = val_str.replace('\'', '')
            except KeyError as e:
                raise e
            dst = '\'%s\'' % val_str
            return dst

        if record.levelno >= self._level_no:
            attrs = ','.join(self._db_clm_names)
            val_list = [_get_val(record, k) for k in self._db_clm_names]
            vals = ','.join(val_list)
            self._db_conn.insert_into(self._table_name, attrs, vals)
