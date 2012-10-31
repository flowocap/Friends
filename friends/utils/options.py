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

"""friends-service command line option parsing."""


__all__ = [
    'Options',
    ]


import argparse


class Options:
    """Command line options parsing."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description='The Friends backend dbus service.')

        self.parser.add_argument(
            '-d', '--debug',
            action='store_true', default=False,
            help='Enable debug level log messages.')
        self.parser.add_argument(
            '-o', '--console',
            action='store_true', default=False,
            help='Enable logging to standard output.')
        self.parser.add_argument(
            '-p', '--performance',
            action='store_true', default=False,
            help='Enable performance tuning instrumentation.')
        self.parser.add_argument(
            '--list-protocols',
            action='store_true', default=False,
            help='List all the known protocols and exit.')
        self.parser.add_argument(
            '--test',
            action='store_true', default=False,
            help='Run the dbus service in testing mode.')
