#! /usr/bin/env python

'''Setup file for Unicon Plugins

See:
    https://packaging.python.org/en/latest/distributing.html
'''

import os
import re
from setuptools import setup, find_packages

def read(*paths):
    '''read and return txt content of file'''
    with open(os.path.join(*paths)) as fp:
        return fp.read()

def find_version(*paths):
    '''reads a file and returns the defined __version__ value'''
    version_match = re.search(r"^__version__ ?= ?['\"]([^'\"]*)['\"]",
                              read(*paths), re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")

def build_version_range(version):
    '''
    for any given version, return the major.minor version requirement range
    eg: for version '3.4.7', return '>=3.4.0, <3.5.0'
    '''
    non_local_version = version.split('+')[0]
    req_ver = non_local_version.split('.')
    if 'rc' in version:
        version_range = '>= %s.%s.0rc0, < %s.%s.0' % \
            (req_ver[0], req_ver[1], req_ver[0], int(req_ver[1])+1)
    else:
        version_range = '>= %s.%s.0, < %s.%s.0' % \
            (req_ver[0], req_ver[1], req_ver[0], int(req_ver[1])+1)

    return version_range

def version_info(*paths):
    '''returns the result of find_version() and build_version_range() tuple'''

    version = find_version(*paths)
    return version, build_version_range(version)

# compute version range
version, version_range = version_info('src', 'unicon', 'plugins', '__init__.py')

install_requires = ['unicon {range}'.format(range = version_range),
                    'pyyaml',
                    'PrettyTable',
                    'cryptography>=43.0']

# launch setup
setup(
    name = 'unicon.plugins',
    version = version,

    # descriptions
    description = 'Unicon Connection Library Plugins',
    long_description = read('DESCRIPTION.rst'),

    # the project's main homepage.
    url = 'https://developer.cisco.com/pyats',

    # author details
    author = 'Cisco Systems Inc.',
    author_email = 'pyats-support-ext@cisco.com',

    # project licensing
    license = 'Apache 2.0',

    # see https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
    'Development Status :: 6 - Mature',
    'Development Status :: 5 - Production/Stable',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: Telecommunications Industry',
    'Intended Audience :: Information Technology',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: MacOS',
    'Operating System :: POSIX :: Linux',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3 :: Only',
    'Programming Language :: Python :: Implementation :: CPython',
    'Topic :: Software Development :: Testing',
    'Topic :: Software Development :: Build Tools',
    'Topic :: Software Development :: Libraries',
    'Topic :: Software Development :: Libraries :: Python Modules',
    ],

    # project keywords
    keywords = 'unicon connection pyats cisco',

    # project packages
    packages = ['unicon.%s' %i for i in find_packages(where = 'src/unicon')],

    # project directory
    package_dir = {
        '': 'src',
    },

    # additional package data files that goes into the package itself
    package_data = {'': ['README.rst',
                         'tests/mock_data/*/*.yaml',
                         'tests/mock_data/*/*.txt',
                         'tests/mock_data/*/*/*.txt',
                         'tests/unittest/ssh_host_key',
                         'pid_tokens.csv'
                         ]},

    # Standalone scripts
    scripts = [
    ],

    # package dependencies
    install_requires = install_requires,

    # any additional groups of dependencies.
    # install using: $ pip install -e .[dev]
    #
    # NOTE: asyncssh is also a dev dependency needed to run unit test,
    # but is left off the list to allow continued python 3.4 support.
    extras_require = {
        'dev': ['setuptools',
                'pip',
                'wheel',
                'coverage',
                'restview',
                'Sphinx',
                'sphinxcontrib-napoleon',
                'sphinxcontrib-mockautodoc',
                'sphinx-rtd-theme'],
    },

    # any data files placed outside this package.
    # See: http://docs.python.org/3.4/distutils/setupscript.html
    # format:
    #   [('target', ['list', 'of', 'files'])]
    # where target is sys.prefix/<target>
    data_files = [],

    # non zip-safe (never tested it)
    zip_safe = False,
)
