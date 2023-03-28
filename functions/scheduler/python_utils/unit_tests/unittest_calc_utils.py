'''
unittest_calc_utils.py
'''

import unittest

import os
import sys

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.join(CDIR, '..'))
from utils.logger import logger
from utils.calc_utils import calc_deg_from_tar_size

logger.setLevel('CRITICAL')

# logger.setLevel('DEBUG')


class TestCalcUtils(unittest.TestCase):
    def test_calc_deg_from_tar_size(self):
        test_cases = [
            [10, 0.10, 0.57295],
            [10, 0.15, 0.85942],
            [10, 0.20, 1.14587],
            [15, 0.10, 0.38197],
            [15, 0.15, 0.57295],
            [15, 0.20, 0.76393],
            [20, 0.10, 0.28647],
            [20, 0.15, 0.42971],
            [20, 0.20, 0.57295],
        ]
        for test_case in test_cases:
            range_meter, tar_size_meter, ans = test_case
            res = calc_deg_from_tar_size(range_meter, tar_size_meter)
            self.assertAlmostEqual(res, ans, places=4)


if __name__ == '__main__':
    unittest.main()
