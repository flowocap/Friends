# friends-dispatcher -- send & receive messages from any social network
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
from friends.tests.mocks import mock


class TestLogging(unittest.TestCase):
    """Test the logging utilities."""

    @mock.patch('friends.utils.logging.logging')
    @mock.patch('friends.utils.logging.os')
    def test_initialize(self, os_mock, log_mock):
        os_mock.path.dirname.return_value = '/dev'
        initialize(filename='/dev/null')
        os_mock.makedirs.assert_called_once_with('/dev')
        os_mock.path.dirname.assert_called_once_with('/dev/null')

        rot = log_mock.handlers.RotatingFileHandler
        rot.assert_called_once_with(
            '/dev/null', maxBytes=20971520, backupCount=5)
        log_mock.Formatter.assert_called_with(
            '{levelname:5}  {threadName:10}  {asctime}  {name:18}  {message}',
            style='{')
        rot().setFormatter.assert_called_once_with(log_mock.Formatter())

        log_mock.getLogger.assert_called_once_with()
        log_mock.getLogger().setLevel.assert_called_once_with(log_mock.INFO)
        log_mock.getLogger().addHandler.assert_called_once_with(rot())

    @mock.patch('friends.utils.logging.logging')
    @mock.patch('friends.utils.logging.os')
    def test_initialize_console(self, os_mock, log_mock):
        os_mock.path.dirname.return_value = '/dev'
        initialize(True, True, filename='/dev/null')
        os_mock.makedirs.assert_called_once_with('/dev')
        os_mock.path.dirname.assert_called_once_with('/dev/null')

        stream = log_mock.StreamHandler
        stream.assert_called_once_with()
        log_mock.Formatter.assert_called_with(
            '{levelname:5}  {threadName:10}  {name:18}  {message}',
            style='{')
        stream().setFormatter.assert_called_once_with(log_mock.Formatter())

        log_mock.getLogger.assert_called_once_with()
        log_mock.getLogger().setLevel.assert_called_once_with(log_mock.DEBUG)
        log_mock.getLogger().addHandler.assert_called_with(stream())
