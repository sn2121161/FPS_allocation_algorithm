import os
import sys

CDIR = os.path.abspath(os.path.dirname(__file__))
UTIL_DIR = os.path.join(CDIR, '..')
sys.path.append(UTIL_DIR)


def main():
    from utils.logger import logger
    logger.debug('DEBUG')
    logger.info('INFO')
    logger.warning('WARN')
    logger.error('ERROR')
    logger.critical('CRITICAL')
    logger.exception('exception')
    logger.exception(Exception("exception"))


def main2():
    from logging import getLogger
    from logging import Formatter
    from logging import StreamHandler
    from io import StringIO
    logger = getLogger(__name__)
    fmt = '|'.join([
        '%(asctime)s',
        '%(levelname)s',
        '%(filename)s(%(lineno)d)',
        '%(funcName)s',
        '%(message)s',
    ])
    log_stream = StringIO()
    formatter = Formatter(fmt)
    handler = StreamHandler(log_stream)
    handler.setFormatter(formatter)

    some_handler = StreamHandler()
    some_handler.setFormatter(formatter)

    some_other_handler = StreamHandler(log_stream)
    some_other_handler.setFormatter(formatter)

    logger.addHandler(some_handler)
    logger.addHandler(some_other_handler)

    logger.info('hello world')
    logger.warning('be careful!')
    logger.debug("you won't see this")
    logger.error('you will see this')
    logger.critical('critical is logged too!')
