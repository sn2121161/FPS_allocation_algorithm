'''
unittest_specifit_time.py
'''

import unittest

import os
import sys
from datetime import datetime

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.join(CDIR, '..'))
from utils.logger import logger
from utils.start_and_end_time import StartAndEndTime

logger.setLevel('CRITICAL')

# logger.setLevel('DEBUG')


class TestStartEndTime(unittest.TestCase):

    def test_2022_03_31(self):
        hours = 7
        now = datetime(2022, 3, 31, 11, 11, 11)
        data = {
            'hours_before_and_end_of_today': (
                '2022-03-31 16:59:59',
                '2022-03-31 23:59:59',
            ),
            'hours_before_and_end_of_last_month': (
                '2022-02-28 16:59:59',
                '2022-02-28 23:59:59',
            ),
            'hours_before_and_now': (
                '2022-03-31 04:11:11',
                '2022-03-31 11:11:11',
            ),
            'hours_before_and_start_of_today': (
                '2022-03-30 17:00:00',
                '2022-03-31 00:00:00',
            ),
        }
        saet = StartAndEndTime(now)
        for method_name, ans in data.items():
            res = getattr(saet, method_name)(hours)
            self.assertEqual(res, ans)
        data = {
            'bgn_and_end_of_today': (
                '2022-03-31 00:00:00',
                '2022-03-31 23:59:59',
            ),
        }
        for method_name, ans in data.items():
            res = getattr(saet, method_name)()
            self.assertEqual(res, ans)

    def test_2022_02_02(self):
        hours = 7
        now = datetime(2022, 2, 2, 22, 22, 22)
        data = {
            'hours_before_and_end_of_today': (
                '2022-02-02 16:59:59',
                '2022-02-02 23:59:59',
            ),
            'hours_before_and_end_of_last_month': (
                '2022-01-31 16:59:59',
                '2022-01-31 23:59:59',
            ),
            'hours_before_and_now': (
                '2022-02-02 15:22:22',
                '2022-02-02 22:22:22',
            ),
            'hours_before_and_start_of_today': (
                '2022-02-01 17:00:00',
                '2022-02-02 00:00:00',
            ),
        }
        saet = StartAndEndTime(now)
        for method_name, ans in data.items():
            res = getattr(saet, method_name)(hours)
            self.assertEqual(res, ans)
        data = {
            'bgn_and_end_of_today': (
                '2022-02-02 00:00:00',
                '2022-02-02 23:59:59',
            ),
        }
        for method_name, ans in data.items():
            res = getattr(saet, method_name)()
            self.assertEqual(res, ans)


if __name__ == '__main__':
    unittest.main()
