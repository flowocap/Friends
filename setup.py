# friends -- send & receive messages from any social network
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

import sys

from setuptools import setup, find_packages


if sys.version_info[:2] < (3, 2):
    raise RuntimeError('Python 3.2 or newer required')


setup(
    name='friends',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    package_data = {
        'friends.service.templates': ['*.service.in'],
        'friends.tests.data': ['*.dat'],
        },
    data_files = [
        ('/usr/share/glib-2.0/schemas',
         ['data/com.canonical.friends.gschema.xml']),
        ('/usr/share/friends',
         ['data/model-schema.csv']),
        ],
    entry_points = {
        'console_scripts': ['friends-dispatcher = friends.main:main'],
        'distutils.commands': [
            'install_service_files = '
                'friends.utils.install:install_service_files',
            ],
        },
    test_requires = [
        'mock',
        ],
    )
