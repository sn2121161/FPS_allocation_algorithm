import numpy as np


def calc_deg_from_tar_size(range_meter, tar_size_meter):
    '''
    Argvs
    range_meter: float, list or np.array
                 range in meter between unit and the target (d)
    target_size_meter: float, target size in meter (x)

    Returns:
    dst: degree of target (t)

        ___
        /|\
       / t \
      /  |  \
     /   |   \
    /    |d   \
   /     |     \
  |-------------|
         x
    t' = arctan(x' / d)
    t' = t / 2
    x' = x / 2
    t = 2 * arctan((x / (2 * d)))

    '''
    if not isinstance(tar_size_meter, np.ndarray):
        tar_size_arr = np.array(tar_size_meter)
    else:
        tar_size_arr = tar_size_meter
    dst = 2 * np.rad2deg(np.arctan(tar_size_arr / (2 * range_meter)))
    return dst
