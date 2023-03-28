import os
import sys
import re
import numpy as np

CDIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(CDIR)
from logger import logger


def split_by_capitals(src_str):
    dst = re.findall('.[^A-Z]*', src_str)
    return dst


def gen_array_plot_txt(src, x_width=1, n_yticks=20):
    if src.ndim == 1:
        tmp = src[np.newaxis, :]
    else:
        tmp = src
    ymax = tmp.max()
    ymin = tmp.min()
    tmp = np.round((tmp - ymin) / (ymax - ymin) * n_yticks).astype(int)
    yticks = {
        0: '%7.2f+' % ymax,
        n_yticks: '%7.2f+' % ymin,
        int(n_yticks / 2): '%7.2f+' % ((ymax - ymin) / 2 + ymin),
    }
    mrk = '*'
    for j, vec in enumerate(tmp):
        txt_arr = [[' ' * x_width for i in range(tmp.shape[1])]
                   for j in range(n_yticks + 1)]
        txt_list = []
        txt_list.append('src[%d, :] = ' % j)
        txt_list.append('%s.%s.' % (' ' * 7, '-' * x_width * tmp.shape[1]))
        for i, val in enumerate(vec):
            txt_arr[val][i] = mrk * x_width
        for i, txt in enumerate(txt_arr[::-1]):
            txt = '%s%s|' % (yticks.get(i, '%7s|' % ' '), ''.join(txt))
            txt_list.append(txt)
        txt_list.append('%s\'%s\'' % (' ' * 7, '-' * x_width * tmp.shape[1]))
        txt = ''.join([
            ' ' * 8,
            '%d' % 0,
            ' ' * x_width * tmp.shape[1],
            ' %2d' % tmp.shape[-1],
        ])
        txt_list.append(txt)
    dst = '\n'.join(txt_list)
    return dst


def gen_array_txt(arr, msg, precision=2):
    '''
    print array
    Argvs
    arr: np.ndarray
    '''
    if arr.ndim == 1:
        arr = np.atleast_2d(arr)
    arr_rounded = np.round(arr, decimals=precision)
    digit_len = max([len(str(x)) for x in arr_rounded.flatten()])
    digit_len = max([digit_len, len(str(arr.shape[1]))])
    if digit_len <= precision + 1:
        digit_len += (precision + 1)
    row_idx_len = len(str(arr.shape[0]))
    float_tmp = '{:%d.%df}' % (digit_len, precision)
    clm_idx_tmp = '{:%dd}' % (digit_len)
    row_idx_tmp = '{:%dd}' % (row_idx_len)
    len_x = arr.shape[1]
    txt_brdr = '+'.join(['-' * row_idx_len] +
                        ['-' * digit_len for i in range(len_x)]) + '|'
    txt_xidx = '|'.join([' ' * row_idx_len] +
                        [clm_idx_tmp.format(i) for i in range(len_x)]) + '|'
    str_list = [msg]
    str_list += ['size: %s' % list(arr.shape)]
    str_list += [txt_xidx]
    str_list += [txt_brdr]
    for yi, x1 in enumerate(arr_rounded):
        txt = '|'.join([
            row_idx_tmp.format(yi),
            '|'.join([float_tmp.format(x2) for x2 in x1]),
            row_idx_tmp.format(yi),
        ])
        str_list += [txt]
    str_list += [txt_brdr]
    str_list += [txt_xidx]
    dst = '\n%s' % '\n'.join(str_list)
    return dst


def int_to_ordinal_str(src):
    '''
    Convert integer to ordinal format
    ord_no = int_to_ordinal_str(int_no)

    Argvs
    src: int.   1,   2,   3,   4, ...

    Returns
    dst: str. 1st, 2nd, 3rd, 4th, ...
    '''
    int_no = src if isinstance(src, int) else int(src)
    if str(int_no)[-2:] in ['11', '12', '13']:
        tmp = 0
    else:
        tmp = (int_no / 10 % 10 != 1) * (int_no % 10 < 4) * int_no % 10
    ordsign = 'tsnrhtdd'[tmp::4]
    dst = '%d%s' % (int_no, ordsign)
    return dst


if __name__ == '__main__':
    src = np.random.randn(1, 64) * 200
    print(gen_array_plot_txt(src))
    print(gen_array_plot_txt(src, 2, 20))
    print(gen_array_plot_txt(src, 2, 30))
    src = np.linspace(-1, 1, 64)
    print(gen_array_plot_txt(src))
    print(gen_array_plot_txt(src, 2, 20))
    print(gen_array_plot_txt(src, 2, 30))
