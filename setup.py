# friends-service -- send & receive messages from any social network
# Copyright (C) 2012  Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#import setuptools
#setuptools.use_setuptools()

import sys
from setuptools import setup, find_packages

if sys.version_info[:2] < (3, 2):
    raise RuntimeError('Python 3.2 or newer required')


setup(
    name='friends',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    entry_points = {
        'console_scripts': ['friends-service = friends.main:main'],
        },
    test_requires = [
        'mock',
        ],
    )