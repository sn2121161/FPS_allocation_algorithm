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
from utils.specific_time import SpecificTime

logger.setLevel('CRITICAL')

# logger.setLevel('DEBUG')


class TestSpecificTime(unittest.TestCase):

    def test_february(self):
        data = {
            'now': datetime(2022, 2, 2, 22, 22, 22),
            'start_of_the_day': datetime(2022, 2, 2, 0, 0, 0),
            'start_of_last_day': datetime(2022, 2, 1, 0, 0, 0),
            'start_of_next_day': datetime(2022, 2, 3, 0, 0, 0),
            'start_of_the_week': datetime(2022, 1, 31, 0, 0, 0),
            'start_of_last_week': datetime(2022, 1, 24, 0, 0, 0),
            'start_of_next_week': datetime(2022, 2, 7, 0, 0, 0),
            'start_of_the_month': datetime(2022, 2, 1, 0, 0, 0),
            'start_of_last_month': datetime(2022, 1, 1, 0, 0, 0),
            'start_of_next_month': datetime(2022, 3, 1, 0, 0, 0),
            'end_of_the_day': datetime(2022, 2, 2, 23, 59, 59),
            'end_of_last_day': datetime(2022, 2, 1, 23, 59, 59),
            'end_of_next_day': datetime(2022, 2, 3, 23, 59, 59),
            'end_of_the_week': datetime(2022, 2, 6, 23, 59, 59),
            'end_of_next_week': datetime(2022, 2, 13, 23, 59, 59),
            'end_of_last_week': datetime(2022, 1, 30, 23, 59, 59),
            'end_of_the_month': datetime(2022, 2, 28, 23, 59, 59),
            'end_of_next_month': datetime(2022, 3, 31, 23, 59, 59),
            'end_of_last_month': datetime(2022, 1, 31, 23, 59, 59),
        }
        hours = 7
        st = SpecificTime(data['now'])
        for method_name, ans in data.items():
            self.assertEqual(ans, getattr(st, method_name)())

    def test_march(self):
        data = {
            'now': datetime(2022, 3, 30, 17, 33, 41),
            'start_of_the_day': datetime(2022, 3, 30, 0, 0, 0),
            'start_of_last_day': datetime(2022, 3, 29, 0, 0, 0),
            'start_of_next_day': datetime(2022, 3, 31, 0, 0, 0),
            'start_of_the_week': datetime(2022, 3, 28, 0, 0, 0),
            'start_of_last_week': datetime(2022, 3, 21, 0, 0, 0),
            'start_of_next_week': datetime(2022, 4, 4, 0, 0, 0),
            'start_of_the_month': datetime(2022, 3, 1, 0, 0, 0),
            'start_of_last_month': datetime(2022, 2, 1, 0, 0, 0),
            'start_of_next_month': datetime(2022, 4, 1, 0, 0, 0),
            'end_of_the_day': datetime(2022, 3, 30, 23, 59, 59),
            'end_of_last_day': datetime(2022, 3, 29, 23, 59, 59),
            'end_of_next_day': datetime(2022, 3, 31, 23, 59, 59),
            'end_of_the_week': datetime(2022, 4, 3, 23, 59, 59),
            'end_of_last_week': datetime(2022, 3, 27, 23, 59, 59),
            'end_of_next_week': datetime(2022, 4, 10, 23, 59, 59),
            'end_of_the_month': datetime(2022, 3, 31, 23, 59, 59),
            'end_of_last_month': datetime(2022, 2, 28, 23, 59, 59),
            'end_of_next_month': datetime(2022, 4, 30, 23, 59, 59),
        }
        st = SpecificTime(data['now'])
        for method_name, ans in data.items():
            self.assertEqual(ans, getattr(st, method_name)())


if __name__ == '__main__':
    unittest.main()
