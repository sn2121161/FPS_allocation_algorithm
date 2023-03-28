'''
setup.py
'''

import os
import shutil
import glob

from setuptools import setup
from setuptools import find_packages
from setuptools import Command


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
    name='allocation',
    version='0.0.1',
    description='vehilce-journey allocatio',
    author='Sofia Taylor',
    author_email='sofia.taylor@flexpowerltd.com',
    install_requires=read_requirements(),
    packages=find_packages(exclude=('tests')),
    cmdclass={
        'clean': CleanCommand,
    },
)
