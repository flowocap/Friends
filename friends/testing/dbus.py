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

"""Helper for testing the Friends service via dbus over a separate test bus.

These are actually integration tests, not unit tests, although we use Python's
unittest framework to run them.  They require the `friends-service` executable
to be installed next to sys.executable, which is the case in a virtualenv.

If the virtualenv is not set up, a flag will be set in the Controller
instance, which the unittest suite can use to skip these integration tests.

So in summary, in order to run the dbus tests, you must:

$ virtualenv --system-site-packages -p python3 /some/path
$ source /some/path/bin/activate
$ python -m unittest discover -vv

You can run the normal unittests without sourcing the virtualenv.
"""


__all__ = [
    'Controller',
    ]


import os
import sys
import errno
import shutil
import signal
import tempfile
import subprocess

from distutils.spawn import find_executable
from pkg_resources import resource_string


SERVICES = [
    'com.canonical.Friends.Connection',
    'com.canonical.Friends.Service',
    'com.canonical.Friends.Test',
    'com.canonical.Friends.URLShorten',
    ]


class Controller:
    """Start and stop the Friends dbus service under test."""

    def __init__(self):
        self.dbus_address = None
        self.daemon_pid = None
        self.tempdir = tempfile.mkdtemp()
        self.config_path = None
        self.old_envar = None
        self.is_runnable = False

    def _setup(self):
        # Set up the dbus-daemon session configuration file.
        template = resource_string('friends.testing', 'dbus-session.conf.in')
        # resource_string() returns a bytes, but we need a string.
        template = template.decode('utf-8')
        config = template.format(TMPDIR=self.tempdir)
        self.config_path = os.path.join(self.tempdir, 'dbus-session.conf')
        with open(self.config_path, 'w', encoding='utf-8') as fp:
            fp.write(config)
        # Now we have to set up the .service files.  This is a bit of a hack
        # because to be successfully set up, the Friends backend service must
        # be installed in a virtualenv.  It cannot be run from the source
        # directory because the `friends-service` executable is crafted by a
        # setuptools entry point.  We'll set the `is_runnable` flag if
        # everything looks good, and the unittest suite can just skip these
        # tests if they don't.  They're integration tests anyway.
        bindir = os.path.dirname(sys.executable)
        exe = os.path.join(bindir, 'friends-service')
        # Make sure the file exists and is callable.
        try:
            # All we care about is a zero exit status.
            with open('/dev/null', 'w') as devnull:
                subprocess.check_call([exe, '--help'],
                                      stdout=devnull, stderr=devnull)
        # In Python 3.3, use FileNotFoundError and discard the errno check.
        except OSError as error:
            if error.errno == errno.ENOENT:
                # There is no friends-service executable, so skip these tests.
                return
            raise
        except subprocess.CalledProcessError:
            # We'll just skip these tests.
            return
        # One little complication.  In an installed system,
        # /usr/bin/friends-service will exist, right next to /usr/bin/python3.
        # That's not the thing we want to test, so we do one more check.
        # There better be an `activate` file there too.  This could break if
        # the system happens to also have a /usr/bin/activate, but that
        # doesn't exist on Ubuntu as of 12.10.
        if not os.path.exists(os.path.join(bindir, 'activate')):
            return
        self.is_runnable = True
        for service in SERVICES:
            service_file = service + '.service'
            template = resource_string('friends.service.templates',
                                       service_file + '.in')
            template = template.decode('utf-8')
            service_contents = template.format(BINDIR=bindir, ARGS='--test')
            service_path = os.path.join(self.tempdir, service_file)
            with open(service_path, 'w', encoding='utf-8') as fp:
                fp.write(service_contents)

    def start(self):
        """Start the Friends service in a subprocess.

        Use the output from dbus-daemon to gather the address and pid of the
        service in the subprocess.  We'll use those in the foreground process
        to talk to our test instance of the service (rather than any similar
        service running normally on the development desktop).
        """
        daemon_exe = find_executable('dbus-daemon')
        if daemon_exe is None:
            raise RuntimeError('Cannot find the `dbus-daemon` executable.')
        self._setup()
        if not self.is_runnable:
            return
        dbus_args = [
            daemon_exe,
            '--fork',
            '--config-file=' + self.config_path,
            # Return the address and pid on stdout.
            '--print-address=1',
            '--print-pid=1',
            ]
        stdout = subprocess.check_output(dbus_args, bufsize=4096)
        lines = stdout.splitlines()
        self.dbus_address = lines[0].strip().decode('utf-8')
        self.daemon_pid = int(lines[1].strip())
        #print('address:', self.dbus_address, 'pid:', self.daemon_pid)
        # Set the service's address into the environment for rendezvous.
        self.old_envar = os.environ.get('DBUS_SESSION_BUS_ADDRESS')
        os.environ['DBUS_SESSION_BUS_ADDRESS'] = self.dbus_address

    def shutdown(self):
        if self.old_envar is not None:
            os.environ['DBUS_SESSION_BUS_ADDRESS'] = self.old_envar
            self.old_envar = None
        if self.daemon_pid is not None:
            os.kill(self.daemon_pid, signal.SIGTERM)
            self.daemon_pid = None
        if self.tempdir is not None:
            shutil.rmtree(self.tempdir)
            self.tempdir = None
