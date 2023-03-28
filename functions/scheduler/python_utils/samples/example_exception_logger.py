import os
import sys

import requests

import numpy as np

CDIR = os.path.abspath(os.path.dirname(__file__))
UTIL_DIR = os.path.join(CDIR, '../../python_utils')
sys.path.append(UTIL_DIR)
from utils.logger import logger


class Devision():
    def __init__(self):
        self._default_ret = np.inf

    def devided_by_zero(self):
        '''
        calculate 1 / 0, then raise error
        '''
        logger.debug('calculate 1 / 0')
        try:
            dst = 1 / 0
        except ZeroDivisionError as err:
            logger.exception(err)
            raise err
        except Exception as err:
            logger.exception(err)
            raise err
        return dst

    def devided_by_zero_and_fix_by_inf(self):
        '''
        calculate 1 / 0, then, fix the value by np.inf
        '''
        logger.debug('calculate 1 / 0')
        try:
            dst = 1 / 0
        except ZeroDivisionError as err:
            logger.warning(f'{err}. return {self._default_ret}.')
            dst = self._default_ret
            raise err
        except Exception as err:
            logger.exception(err)
            return dst


def requests_exception(url: int) -> dict:
    try:
        request = requests.get(url)
        request.raise_for_status()
    except requests.exceptions.HTTPError as err:
        logger.exception(err)
        raise err
    except requests.ConnectionError as err:
        logger.exception(err)
        raise err
    except requests.exceptions.Timeout as err:
        logger.exception(err)
        raise err
    except requests.exceptions.TooManyRedirects as err:
        logger.exception(err)
        raise err
    except requests.exceptions.RequestException as err:
        logger.exception(err)
        raise err
    dst = request.json()
    return dst


def request_with_status_code(status_code: int):
    logger.info('requests module exceptions')
    url = 'https://postman-echo.com/status/%d' % status_code
    logger.info('requests exception handling by %s' % url)
    logger.debug('%s' % status_code)
    try:
        ret = requests_exception(url)
    except Exception as err:
        logger.error(err)
        raise err
    logger.info(ret)


def main():
    status_codes = [200, 400, 408, 429, 500]
    for status_code in status_codes:
        try:
            ret = request_with_status_code(status_code)
        except Exception as err:
            logger.warning(err)
            raise SystemExit(err)
        logger.info(ret)


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        logger.error(err)


def main2():
    devision = Devision()
    methods = [
        devision.devided_by_zero,
        devision.devided_by_zero_and_fix_by_inf,
    ]
    logger.info('zero devision exceptions')
    for method in methods:
        logger.debug('%s' % method)
        try:
            ret = method()
        except Exception as e:
            logger.error(e)
            ret = None
        logger.info(f'return value:{ret}')


if __name__ == '__main__':
    try:
        main2()
    except Exception as err:
        logger.error(err)
        raise SystemExit(err)
