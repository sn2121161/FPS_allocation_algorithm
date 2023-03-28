'''
sys_utils.py
some utility functions
'''
import os
import sys
import socket
import struct
import fcntl
import argparse
from argparse import RawTextHelpFormatter

cdir = os.path.abspath(os.path.dirname(__file__))
lib_root = os.path.join(cdir, '..')
sys.path.append(lib_root)
from utils.logger import logger


def y_n_question(msg):
    '''
    dst = y_n_question(cnd, msg)

    Argvs:
    msg: printing message

    Return:
    dst: bool: True if Y or y, False if N or n.
    '''
    input_str = input('%s (Y/N):' % msg)
    check = str(input_str).lower().strip()
    if check == 'y':
        dst = True
    elif check == 'n':
        dst = False
    else:
        print('Invalid Input: %s' % input_str)
        dst = y_n_question(msg)
    return dst


def arg_parser_src_dir(description=__file__):
    '''
    args = arg_parser_src_dir()

    Returns
    args: arg parse name space. args.src_dir
    '''
    parser = argparse.ArgumentParser(
        description=description, formatter_class=RawTextHelpFormatter)
    parser.add_argument('src_dir', help='source directory')
    # parser.add_argument('dst_dir', help='distination directory')
    if len(sys.argv) != 2:
        parser.print_help(sys.stderr)
        return None
    args = parser.parse_args()
    return args


def arg_parser_src_dir_dst_dir(description=__file__):
    '''
    args = arg_parser_src_dir()

    Returns
    args: arg parse name space. args.src_dir
    '''
    parser = argparse.ArgumentParser(
        description=description, formatter_class=RawTextHelpFormatter)
    parser.add_argument('src_dir', help='source directory')
    parser.add_argument('dst_dir', help='distination directory')
    if len(sys.argv) != 3:
        parser.print_help(sys.stderr)
        return None
    args = parser.parse_args()
    return args


def arg_parser_src_name_dst_name(description=__file__):
    '''
    args = arg_parser_src_name_dst_name()

    Returns
    args: arg parse name space. args.src_name
    '''
    parser = argparse.ArgumentParser(
        description=description, formatter_class=RawTextHelpFormatter)
    parser.add_argument('src_name', help='source name')
    parser.add_argument('dst_name', help='distination name')
    if len(sys.argv) != 3:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    return args


def get_ip_addr():
    '''
    Returns IP address and interface name of the environment
    ip_addr, ifname = get_ip_addr()

    Argvs
    No argvs

    Returns
    dst_ip: str, ip address
    dst_ifname: str, interface name
    '''

    def _get_interface_ip_addr(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        pack = struct.pack('256s', bytes(ifname[:15], 'utf-8'))
        SIOCGIFADDR = 0x8915
        ioctl = fcntl.ioctl(s.fileno(), SIOCGIFADDR, pack)
        ip = socket.inet_ntoa(ioctl[20:24])
        return ip

    # --- initial dst ip address and interface name
    dst_ip = socket.gethostbyname(socket.gethostname())
    dst_ifname = 'unknown'
    # ---
    interfaces = socket.if_nameindex()
    for idx, ifname in interfaces:
        try:
            ip = _get_interface_ip_addr(ifname)
            if ip.startswith('127.'):
                continue
            dst_ip = ip
            dst_ifname = ifname
            break
        except IOError as ioe:
            logger.debug(ioe)
    return dst_ip, dst_ifname


if __name__ == '__main__':
    ip, ifname = get_ip_addr()
    print(ip, ifname)
