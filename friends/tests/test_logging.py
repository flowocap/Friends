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

"""Test the logging utilities."""

__all__ = [
    'TestLogging',
    ]


import os
import shutil
import logging
import tempfile
import unittest

from friends.utils.logging import initialize


class TestLogging(unittest.TestCase):
    """Test the logging utilities."""

    def setUp(self):
        # Preserve the original logger, but restore the global logging system
        # to pre-initialized state.
        self._logger = logging.getLogger(__name__)
        del logging.Logger.manager.loggerDict[__name__]

    def tearDown(self):
        # Restore the original logger.
        logging.Logger.manager.loggerDict[__name__] = self._logger

    def test_logger_has_filehandler(self):
        initialize()
        # The top level __name__ logger should be available.
        log = logging.getLogger(__name__)
        # Try to find the file opened by the default file handler.
        filenames = []
        for handler in log.handlers:
            if hasattr(handler, 'baseFilename'):
                filenames.append(handler.baseFilename)
        self.assertEqual(len(filenames), 1)

    def _get_log_filename(self, log):
        filenames = []
        for handler in log.handlers:
            if hasattr(handler, 'baseFilename'):
                filenames.append(handler.baseFilename)
        return filenames

    def test_logger_message(self):
        # Write an error message to the log and test that it shows up.
        tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tempdir)
        logfile = os.path.join(tempdir, 'friends-test.log')
        initialize(filename=logfile)
        # Get another handle on the log file.
        log = logging.getLogger(__name__)
        # Try to find the file opened by the default file handler.
        filenames = self._get_log_filename(log)
        self.assertEqual(len(filenames), 1)
        logfile = filenames[0]
        self.assertEqual(os.stat(logfile).st_size, 0)
        # Log messages at INFO or higher should be written.
        log.info('friends at your service')
        self.assertGreater(os.stat(logfile).st_size, 0)
        # Read the contents, which should be just one line of output.
        with open(logfile, encoding='utf-8') as fp:
            contents = fp.read()
        lines = contents.splitlines()
        self.assertEqual(len(lines), 1)
        # The log message will have a variable timestamp at the front, so
        # ignore that, but check everything else.
        self.assertRegex(
            lines[0],
            r'INFO\s+MainThread.*friends.tests.test_logging\s+'
            r'friends at your service')

    def test_console_logger(self):
        # The logger can support an optional console logger.
        tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tempdir)
        logfile = os.path.join(tempdir, 'friends-test.log')
        initialize(console=True, filename=logfile)
        log = logging.getLogger(__name__)
        # Can we do better than testing that there are now two handlers for
        # the logger?
        self.assertEqual(2, sum(1 for handler in log.handlers))

    def test_default_logger_level(self):
        # By default, the logger level is INFO.
        tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tempdir)
        logfile = os.path.join(tempdir, 'friends-test.log')
        initialize(filename=logfile)
        # Get another handle on the log file.
        log = logging.getLogger(__name__)
        # Try to find the file opened by the default file handler.
        filenames = self._get_log_filename(log)
        self.assertEqual(len(filenames), 1)
        logfile = filenames[0]
        # By default, debug messages won't get written since they are less
        # severe than INFO.
        log.debug('friends is ready')
        self.assertEqual(os.stat(logfile).st_size, 0)

    def test_debug_logger_level(self):
        # Set the logger up for debugging.
        tempdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tempdir)
        logfile = os.path.join(tempdir, 'friends-test.log')
        initialize(filename=logfile, debug=True)
        # Get another handle on the log file.
        log = logging.getLogger(__name__)
        # Try to find the file opened by the default file handler.
        filenames = self._get_log_filename(log)
        self.assertEqual(len(filenames), 1)
        logfile = filenames[0]
        log.debug('friends is ready')
        self.assertGreater(os.stat(logfile).st_size, 0)
        # Read the contents, which should be just one line of output.
        with open(logfile, encoding='utf-8') as fp:
            contents = fp.read()
        lines = contents.splitlines()
        self.assertEqual(len(lines), 1)
        # The log message will have a variable timestamp at the front, so
        # ignore that, but check everything else.
        self.assertRegex(
            lines[0],
            r'DEBUG\s+MainThread.*friends.tests.test_logging\s+'
            r'friends is ready')
