# Logger module
`utils/logger.py` is a module to utilise Pytho nlogging facilities.
Log messages are streamed with defined formatting.
Additionally, under some conditions, this logger sends log messages
to a table in the DB by DB handler.

## Specification

### Configuration
The logging configuration is hard-coded at the top of `logger.py`.
```
config_dat = {
    'level': 'INFO',
    'datefmt': '%Y-%m-%d %H:%M:%S',
    'fmt_separator': '|',
    'additional_attrs': {},
    'enable_db_logger': True,
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
    'db_otioin': '-c search_path=log',
    'format': [
        '%(asctime)s',
        '%(levelname)s',
        '%(filename)s(%(lineno)d)',
        '%(funcName)s',
        '%(message)s',
    ],
}
```
- level: logging level
- datefmt: date time format
- fmt_separator: format separator
- additional_attrs: additional attributes
- enable_db_logger: flag to enable db handler
- module_name: module name
- level_db: level to send message to DB
- log_table_name: log table name
- target_column_name: target column name in log_table_name
- modules_table: modules table name
- source_column_name: module ID number column name in module_table
- db_user: db username
- db_pswd: db password
- db_name: db name
- db_host: db host
- db_port: db port
- db_otioin: db option
- format: format list

Note: In the `main` branch, `enable_db_logger` is set False. In `log_db_handler_on` branch, `enable_db_logger` is set True.

[LogRecord attributes](https://docs.python.org/3/library/logging.html#logrecord-attributes) for more details of formatting.

### Conditions of DB handler
The dbhandler will be activated if the conditions below are satisfied.
- enable_do_logger is True (default True)
- The connection to the DB has been established
- Environmental value `WEBSITE_SITE_NAME` exists
`WEBSITE_SITE_NAME` is a environmental variable in Azure environemnt to provide the application's name.

Note: In the main branch, enable_db_logger is set False. In log_db_handler_on branch, enable_db_logger is set True.

# How to use
## Git Submodule
See [git_submodules.md](git_submodules.md)

### Adding git submodule
Run this command in your repository directory.
```
git submodule add ../python_utils.git
```
An empty directory `python_utils` and `.gitmodules` file will be created.

### Updating submodule in local
Run this command to fill the contents in `python_utils` directory.
```
git submodule update --init --recursive
```

### Applying the submodule to remote
Run this command to apply this change to the remote repository.
```
git push
```

### Cloning a repository with submodules
```
git clone --recurse-submodules <URL_PATH>
```

### Pulling all changes in the repositpry including the changes in the submodules
```
git pull --recurse-submodules
```

## import logger module
```
CDIR = os.path.dirname(os.path.abspath(__file__))
PY_UTILS_DIR = os.path.abspath(
    os.path.join(CDIR, 'RELATIVE_PATH_TO', 'python_utils', '..'))

sys.path.append(PY_UTILS_DIR)
from python_utils.utils.logger import logger
```

## Virtual environment
### Create virtual environment
```
python -m venv .venv
source .venv/bin/activate
```

### Installing
```
pip install -r requirements.txt
python setup.py install
```

## using logger
```
logger.debug(log_msg)
logger.info(log_msg)
logger.warning(log_msg)
logger.error(log_msg)
logger.critical(log_msg)
```

## Logging level
There are 5 log levels
- debug
- info
- warning
- error
- critical

Additionally, logger module has exception() method.
It is very controversial and confusing which level should be used.
Although the levels depend on developers opinion,
some guideline of the use of log levels are as follows.

### exception
When raising exceptions, use logger.exception() to report the exceptions.
This is not actually a logging level. However, Python logging module has
a method to report messages with `error` level and exception info.

### debug
This log level is literally for debugging and for coders.
This level is usually used for showing information to the developers
who write codes. This level shouldn't be seen in a production environment
by controlling logger level.

### info
This level is used for showing information to the users.
This level is useful to show,
- Signs of the processes in the scripts, e.g. start and end of slower processes
- Some results of the scripts that are useful to the users.
- Properly handled exceptions
This level also doesn't have to be seen in a production environment.

### warning
This is used for showing potential errors. For example,
- Library version dependencies
- Temporally handled the exceptions
This should be shown in the production setting.

### error
This is used for processes critical and shouldn't be occurred. Like Exception.
This must be shown in any environment.

### critical
This level can be used errors that affect other systems.

# Reference
[Logging facility for Python](https://docs.python.org/3/library/logging.html)
