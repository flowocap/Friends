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

import os
import sys

from pkg_resources import resource_listdir, resource_string
from setuptools import setup, find_packages


if sys.version_info[:2] < (3, 2):
    raise RuntimeError('Python 3.2 or newer required')


# I wish we could use data_files in the setup() below, but we can't because we
# have templates in our source tree and we need to transform them into the
# actual .service files.  Still, it's better to have one copy of the service
# files than multiple ones that would have to stay in sync (i.e. the templates
# for the tests, and the ones installed for the service).
def make_service_files():
    bindir = os.path.dirname(sys.executable)
    # Make sure the destination directory exists.  Generally it will when
    # installed in a real system, but won't when installed in a virtualenv
    # (what about a package build?).
    destdir = os.path.join(sys.prefix, 'share', 'dbus-1', 'services')
    os.makedirs(destdir, exist_ok=True)
    for filename in resource_listdir('friends.service', 'templates'):
        if not filename.endswith('.service.in'):
            continue
        template = resource_string('friends.service.templates', filename)
        template = template.decode('utf-8')
        contents = template.format(BINDIR=bindir, ARGS='')
        target_filename, ext = os.path.splitext(filename)
        assert ext == '.in'
        service_path = os.path.join(destdir, target_filename)
        with open(service_path, 'w', encoding='utf-8') as fp:
            fp.write(contents)


make_service_files()

setup(
    name='friends',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    package_data = {
        'friends.service.templates': ['*.service.in'],
        },
    entry_points = {
        'console_scripts': ['friends-service = friends.main:main'],
        },
    test_requires = [
        'mock',
        ],
    )
