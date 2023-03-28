'''
unittest_str_utils.py
'''

import unittest

import os
import sys

import numpy as np

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.join(CDIR, '..'))
from utils.logger import logger
from utils.str_utils import split_by_capitals
from utils.str_utils import gen_array_plot_txt
from utils.str_utils import gen_array_txt
from utils.str_utils import int_to_ordinal_str

logger.setLevel('CRITICAL')

# logger.setLevel('DEBUG')


class TestStrUtils(unittest.TestCase):
    def _dump_str_list(self, filename, str_list):
        with open(filename, 'w') as fpw:
            for v in str_list:
                fpw.write(v)

    def _diff_txt(self, filename_res, filename_ans):
        cmd = 'diff %s %s' % (filename_res, filename_ans)
        try:
            with os.popen(cmd) as stream:
                diff_out = stream.read()
        except Exception as e:
            raise e
        return diff_out

    def test_split_by_capitals(self):
        '''
        '''
        src_list = [
            'Abc',
            'Defg',
            'Hi-j',
            'K',
            'Lm_n',
            'O0pq9',
            'R?stu',
            'Vv',
            'Wx#',
            'Y|z',
        ]
        dst_list = split_by_capitals(''.join(src_list))
        self.assertEqual(len(dst_list), len(src_list))
        for s, d in zip(src_list, dst_list):
            self.assertEqual(s, d)
        src_list = ['abc', 'defg', 'hi0j']
        dst_list = split_by_capitals(''.join(src_list))
        self.assertNotEqual(len(dst_list), len(src_list))

    def test_gen_array_plot_txt(self):
        '''
        '''
        # --- test files
        filename_res = os.path.join(CDIR, 'gen_array_plot_txt.txt')
        filename_ans = os.path.join(CDIR, 'str_utils_test_cases',
                                    'gen_array_plot_txt.txt')
        # --- test cases
        arr_list = [
            np.linspace(0, 10, 20),
            np.linspace(0, 10, 100).reshape(10, 10),
            np.linspace(0, 1, 20),
            np.linspace(0, 1, 100).reshape(10, 10),
            np.linspace(0, 1, 20),
            np.linspace(0, 1, 100).reshape(10, 10),
            np.linspace(-10, 10, 20),
            np.linspace(-10, 10, 100).reshape(10, 10),
        ]
        # --- exec test cases
        str_list = []
        for arr in arr_list:
            str_list += gen_array_plot_txt(arr, x_width=1, n_yticks=20)
            str_list += gen_array_plot_txt(arr, x_width=1, n_yticks=30)
            str_list += gen_array_plot_txt(arr, x_width=1, n_yticks=40)
            str_list += gen_array_plot_txt(arr, x_width=2, n_yticks=20)
            str_list += gen_array_plot_txt(arr, x_width=2, n_yticks=30)
            str_list += gen_array_plot_txt(arr, x_width=2, n_yticks=40)
        # --- dump res
        self._dump_str_list(filename_res, str_list)
        # --- check diff against truth
        diff_out = self._diff_txt(filename_res, filename_ans)
        self.assertEqual(len(diff_out), 0)
        # --- remove res
        os.system('rm -rf %s' % filename_res)

    def test_gen_array_txt(self):
        '''
        '''
        # --- test files
        filename_res = os.path.join(CDIR, 'gen_array_txt.txt')
        filename_ans = os.path.join(CDIR, 'str_utils_test_cases',
                                    'gen_array_txt.txt')
        if os.path.exists(filename_res):
            os.system('rm -rf %s' % filename_res)
        # --- test cases
        arr_list = [
            np.linspace(0, 10, 20),
            np.linspace(0, 10, 100).reshape(10, 10),
            np.linspace(0, 1, 20),
            np.linspace(0, 1, 100).reshape(10, 10),
        ]
        # --- exec test cases
        str_list = []
        for i, arr in enumerate(arr_list, 1):
            str_list += gen_array_txt(arr, 'test%d-1' % i, precision=1)
            str_list += gen_array_txt(arr, 'test%d-2' % i, precision=2)
            str_list += gen_array_txt(arr, 'test%d-3' % i, precision=3)
        str_list += ['\n']
        # --- dump res
        self._dump_str_list(filename_res, str_list)
        # --- check diff against truth
        diff_out = self._diff_txt(filename_res, filename_ans)
        self.assertEqual(len(diff_out), 0)
        # --- remove res
        os.system('rm -rf %s' % filename_res)

    def test_int_to_ordinal_str(self):
        '''
        '''
        self.assertEqual(int_to_ordinal_str(0), '0th')
        self.assertEqual(int_to_ordinal_str(1), '1st')
        self.assertEqual(int_to_ordinal_str(2), '2nd')
        self.assertEqual(int_to_ordinal_str(3), '3rd')
        self.assertEqual(int_to_ordinal_str(5), '5th')
        self.assertEqual(int_to_ordinal_str(10), '10th')
        self.assertEqual(int_to_ordinal_str(1.0), '1st')
        self.assertEqual(int_to_ordinal_str(1.4), '1st')
        self.assertEqual(int_to_ordinal_str(3.0), '3rd')
        self.assertEqual(int_to_ordinal_str(3.5), '3rd')
        self.assertEqual(int_to_ordinal_str(10), '10th')
        self.assertEqual(int_to_ordinal_str(11), '11th')
        self.assertEqual(int_to_ordinal_str(12), '12th')
        self.assertEqual(int_to_ordinal_str(110), '110th')
        self.assertEqual(int_to_ordinal_str(111), '111th')
        self.assertEqual(int_to_ordinal_str(112), '112th')
        self.assertEqual(int_to_ordinal_str(2010), '2010th')
        self.assertEqual(int_to_ordinal_str(2011), '2011th')
        self.assertEqual(int_to_ordinal_str(2012), '2012th')


if __name__ == '__main__':
    unittest.main()
