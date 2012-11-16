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

"""DBus service file installation helper.

This is used in setup.py to install the real service files. This
module must be cleanly importable with no requirements on non-stdlib
available packages (pkg_resources is okay though).
"""

__all__ = [
    'install_service_files',
    ]


import os
import sys

from distutils.cmd import Command
from pkg_resources import resource_listdir, resource_string


COMMASPACE = ', '


def _do_basic_install(destdir, service_files, args):
    bindir = os.path.dirname(sys.executable)
    for filename in service_files:
        template = resource_string('friends.service.templates', filename)
        template = template.decode('utf-8')
        contents = template.format(BINDIR=bindir, ARGS=args)
        target_filename, ext = os.path.splitext(filename)
        assert ext == '.in'
        service_path = os.path.join(destdir, target_filename)
        with open(service_path, 'w', encoding='utf-8') as fp:
            fp.write(contents)


class install_service_files(Command):
    description = 'Install the DBus service files'

    command_consumes_arguments = True
    user_options = [
        ('root', 'd', 'Root directory containing share/dbus-1/services/'),
        ]

    def initialize_options(self):
        # distutils is insane.  We must set self.root even though the
        # arguments will get passed into .run() via self.args.
        self.args = None
        self.root = None

    def finalize_options(self):
        pass

    def run(self):
        if len(self.args) != 1:
            raise RuntimeError(
                'Bad arguments: {}'.format(COMMASPACE.join(self.args)))
        root_dir = self.args[0]
        # Make sure the destination directory exists.  Generally it will when
        # installed in a real system, but won't when installed in a virtualenv
        # (what about a package build?).
        destdir = os.path.join(root_dir, 'share', 'dbus-1', 'services')
        os.makedirs(destdir, exist_ok=True)
        service_files = [
            filename
            for filename in resource_listdir('friends.service', 'templates')
            if filename.endswith('.service.in')
            ]
        _do_basic_install(destdir, service_files, '-o')
