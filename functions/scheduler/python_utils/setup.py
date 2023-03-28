'''
setup.py
'''

import os
import shutil
import glob

from setuptools import setup
from setuptools import find_packages
from setuptools import Command

name = 'python_utils'
version = '0.0.2'
description = 'python_utils'
author = 'Kiyoto Ichikawa'
author_email = 'Kiyoto.Ichikawa@flexpowerltd.com'
CDIR = os.path.dirname(os.path.abspath(__file__))


def read_requirements():
    '''
    Parse requirements from requirements.txt.
    '''
    requirements = []
    file_name = os.path.join('.', 'requirements.txt')
    with open(file_name, 'r') as f:
        requirements = [line.rstrip() for line in f]
    return requirements


class CleanCommand(Command):
    '''
    Custom clean command to tidy up the project root.
    '''
    clean_targets = [
        'build',
        'dist',
        '*.tgz',
        '*.zip',
        '*.egg-info',
        '__pycache__',
        '*/__pycache__',
        '*/*/__pycache__',
        '*.pyc',
        '*/*.pyc',
        '*/*/*.pyc',
    ]
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for c_t in self.clean_targets:
            for tar in glob.glob(c_t):
                shutil.rmtree(tar)
                print('removed:', tar)


setup(
    name=name,
    version=version,
    description=description,
    author=author,
    author_email=author_email,
    install_requires=read_requirements(),
    packages=find_packages(exclude=('tests')),
    cmdclass={
        'clean': CleanCommand,
    },
)
