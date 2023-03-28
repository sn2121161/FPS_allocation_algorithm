'''
logger.py

logging module

# Usage
## import
CDIR = os.path.abspath(os.path.dirname(__file__))
UTIL_DIR = os.path.join(CDIR, RELATIVE_PATH_TO_UTILS_DIR)
sys.path.append(UTIL_DIR)
from utils.logger import logger

## logger
logger.debug(str)
logger.info(str)
logger.warning(str)
logger.error(str)
logger.critial(str)

## set log level (info)
log_level = 'INFO'
logger.setLevel(log_level)
logger.debug('This won't be seen.')
logger.info('This will be seen.')
logger.warning('This will be seen.')
logger.error('This will be seen.')

## set log level (warning)
log_level = 'WARNING'
logger.setLevel(log_level)
logger.debug('This will NOT be seen.')
logger.info('This will NOT be seen.')
logger.warning('This will be seen.')
logger.error('This will be seen.')

### log levels

### log level list
- 'CRITICAL'
- 'ERROR'
- 'WARNING'
- 'INFO'
- 'DEBUG'

### default log level
- INFO
'''

import os
import sys
from logging import Filter
from logging import getLogger
from logging import StreamHandler
from logging import Formatter
from logging import FileHandler
from logging import getLoggerClass
from collections import namedtuple

CDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CDIR)
from log_db_handler import LogPostgresqlHandler
from log_db_handler import DbConn

config_dat = {
    'level': 'INFO',
    'datefmt': '%Y-%m-%d %H:%M:%S',
    'fmt_separator': '|',
    'additional_attrs': {},
    'enable_db_logger': False,
    'module_name': os.getenv('WEBSITE_SITE_NAME', ''),
    'level_db': 'WARNING',
    'log_table_name': 't_error_log',
    'target_column_name': 'module_no',
    'modules_table': 't_modules',
    'source_column_name': 'module_name',
    'db_user': os.getenv('psgrsql_db_user', ''),
    'db_pswd': os.getenv('psgrsql_db_pswd', ''),
    'db_name': os.getenv('psgrsql_db_name', ''),
    'db_host': os.getenv('psgrsql_db_host', ''),
    'db_port': os.getenv('psgrsql_db_port', ''),
    'db_option': '-c search_path=log',
}
config_dat['format'] = [
    '%(asctime)s',
    '%(levelname)s',
    '%(filename)s(%(lineno)d)',
    '%(funcName)s',
    '%(message)s',
]

Config = namedtuple('config', config_dat)
CONFIG = Config(**config_dat)

loggers = {}


class Logger(getLoggerClass()):
    '''
    Logger class

    logger_cls = Logger()
    '''

    def __init__(self, **args):
        '''
        @Args - All optional
        name: logger name, str, default __name__
        level: log level, str, default level
                  'debug', 'info', 'warn', 'error' or 'clitical'
        datefmt: date time format, str, default, '%Y-%m-%d %H:%M:%S'
        additional_attrs: additional attributes, dict,
                          {name: value, ...}
        '''
        self._name = args.get('name', __name__)
        self._level = args.get('level', CONFIG.level)
        self._datefmt = args.get('datefmt', CONFIG.datefmt)
        self._fmt_separator = args.get('fmt_separator', CONFIG.fmt_separator)
        self._additional_attrs = args.get('additional_attrs',
                                          CONFIG.additional_attrs)

        self._format_list = CONFIG.format

        global loggers
        self._loggers = loggers

        self._formatter = None
        self._logger = None

        self._init_logger()
        self._init_stream_handler()

    def __del__(self):
        pass

    def logger(self):
        return self._logger

    def _init_logger(self):
        # --- global logger container
        self._logger = loggers.get(self._name, None)
        if self._logger is not None:
            map(self._logger.removeHandler, self._logger.handlers[:])
            map(self._logger.removeFilter, self._logger.filters[:])

        # --- loger object
        self._logger = getLogger(self._name)
        self._logger.setLevel(self._level)

        # --- logger handlear initialisation
        if self._logger.handlers:
            self._logger.handlers = []

        # --- global logger container
        self._loggers.update({self._name: self._logger})

        # --- filter
        self._init_filter()

        # --- formatter
        self._init_formatter()

    def _init_formatter(self):
        # --- formatter
        format_str = self._fmt_separator.join(self._format_list)
        self._formatter = Formatter(format_str, datefmt=self._datefmt)

    def _init_filter(self):
        self.add_filter(self._additional_attrs)

    def _init_stream_handler(self):
        # --- stream handler
        handler = StreamHandler()
        handler.setFormatter(self._formatter)
        self.add_handler(handler)

    def add_filter(self, additional_attrs):
        for attr_name, attr_value in additional_attrs.items():
            filt = CustomAttributeFilter(attr_value, attr_name)
            self._logger.addFilter(filt)
            attr_format = filt.attr_format()
            if attr_format != '':
                self._format_list.insert(2, attr_format)

    def add_handler(self, handler):
        self._logger.addHandler(handler)

    def init_file_handler(self, log_filepath):
        # --- file handler
        handler = FileHandler(log_filepath)
        handler.setFormatter(self._formatter)
        self._logger.addHandler(handler)


class CustomAttributeFilter(Filter):
    '''
    '''

    def __init__(self, attr_value: str, attr_name: str, **args: int):
        '''
        attr_value: attribute value
        attr_name: attribute name
        '''
        self._attr_value = attr_value
        self._attr_name = attr_name
        self._attr_format = ''

    def filter(self, record):
        '''
        filter method override
        '''
        if self._attr_value != '':
            record.__dict__.update({self._attr_name: self._attr_value})
        return True

    def attr_format(self):
        '''
        Returns format of this filter for Formatting
        '''
        if self._attr_value != '':
            self._attr_format = ''.join(['%(', self._attr_name, ')s'])
        return self._attr_format


class LoggerWithDb(Logger):
    '''
    Logger module setup class with DB handler.

    logger_cls = LoggerWithDb()
    logger = logger_clas.logger()

    dbhandler will be activated if
    - The connection to the DB has been established
    - Environmental value, "WEBSITE_SITE_NAME" exists
    - enable_do_logger is True (default True)
    '''

    def __init__(self):
        '''
        '''
        self._db = None

        enable_db_logger = CONFIG.enable_db_logger
        self._level_db = CONFIG.level_db
        self._tname_log = CONFIG.log_table_name
        self._cname_tar = CONFIG.target_column_name
        self._tname_modules = CONFIG.modules_table
        self._cname_src = CONFIG.source_column_name
        self._module_name = CONFIG.module_name
        self._db_connect_args = [
            CONFIG.db_user,
            CONFIG.db_pswd,
            CONFIG.db_name,
            CONFIG.db_host,
            CONFIG.db_port,
            CONFIG.db_option,
        ]

        # --- logger setup
        Logger.__init__(
            self,
            level=CONFIG.level,
            datefmt=CONFIG.datefmt,
            fmt_separator=CONFIG.fmt_separator,
            additional_attrs=CONFIG.additional_attrs,
        )
        self._db_conn()
        if enable_db_logger is True:
            self._setup_db_handler()

    def __del__(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def _db_conn(self):
        try:
            self._db = DbConn(*self._db_connect_args)
        except Exception as e:
            self._logger.warning(e)
            self._db = None

    def _get_attrs(self):
        '''
        '''
        if self._db is None:
            attrs = {}
        else:
            attr_name_map = {
                self._cname_tar: (self._cname_src, self._module_name)
            }
            attrs = {
                k: self._db.select(self._tname_modules, k, v[0], v[1])
                for k, v in attr_name_map.items()
            }
        return attrs

    def _setup_db_handler(self):
        if self._module_name == '':
            return

        attrs = self._get_attrs()
        if None in attrs.values():
            self._db.close()
            return

        handler = LogPostgresqlHandler(self._db, self._tname_log,
                                       self._level_db)
        self.add_handler(handler)
        self.add_filter(attrs)


logger_cls = LoggerWithDb()
logger = logger_cls.logger()


def main():
    log_levels = [
        'CRITICAL',
        'ERROR',
        'WARNING',
        'INFO',
        'DEBUG',
    ]
    print_tmp = '--- log level: %s ---'
    log_msg_tmp = 'module: %s, log level: %s'

    for log_lvl in log_levels:
        # log_msg = 'log message'
        print(print_tmp % log_lvl)
        logger.setLevel(log_lvl)
        log_msg = log_msg_tmp % ('debug', log_lvl)
        logger.debug(log_msg)
        log_msg = log_msg_tmp % ('info', log_lvl)
        logger.info(log_msg)
        log_msg = log_msg_tmp % ('warning', log_lvl)
        logger.warning(log_msg)
        log_msg = log_msg_tmp % ('error', log_lvl)
        logger.error(log_msg)
        log_msg = log_msg_tmp % ('critical', log_lvl)
        logger.critical(log_msg)

    for log_lvl in log_levels[::-1]:
        log_msg = 'log level: %s' % log_lvl
        # log_msg = 'log message'
        print(print_tmp % log_lvl)
        logger.setLevel(log_lvl)
        log_msg = log_msg_tmp % ('debug', log_lvl)
        logger.debug(log_msg)
        log_msg = log_msg_tmp % ('info', log_lvl)
        logger.info(log_msg)
        log_msg = log_msg_tmp % ('warning', log_lvl)
        logger.warning(log_msg)
        log_msg = log_msg_tmp % ('error', log_lvl)
        logger.error(log_msg)
        log_msg = log_msg_tmp % ('critical', log_lvl)
        logger.critical(log_msg)


if __name__ == '__main__':
    main()
