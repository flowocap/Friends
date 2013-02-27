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

"""Test the Avatar cacher."""

__all__ = [
    'TestAvatars',
    ]


import os
import time
import shutil
import tempfile
import unittest

from datetime import date, timedelta
from gi.repository import GdkPixbuf
from pkg_resources import resource_filename

from friends.tests.mocks import FakeSoupMessage, mock
from friends.utils.avatar import Avatar


@mock.patch('friends.utils.http._soup', mock.Mock())
class TestAvatars(unittest.TestCase):
    """Test Avatar logic."""

    def setUp(self):
        # Create a temporary cache directory for storing the avatar image
        # files.  This ensures that the user's operational environment can't
        # possibly interfere.
        self._temp_cache = tempfile.mkdtemp()
        self._avatar_cache = os.path.join(
            self._temp_cache, 'friends', 'avatars')

    def tearDown(self):
        # Clean up the temporary cache directory.
        shutil.rmtree(self._temp_cache)

    def test_noop(self):
        # If a tweet is missing a profile image, silently ignore it.
        self.assertEqual(Avatar.get_image(''), '')

    def test_hashing(self):
        # Check that the path hashing algorithm return a hash based on the
        # download url.
        with mock.patch('friends.utils.avatar.CACHE_DIR', self._avatar_cache):
            path = Avatar.get_path('fake_url')
        self.assertEqual(
            path.split(os.sep)[-3:],
            ['friends', 'avatars',
             # hashlib.sha1('fake_url'.encode('utf-8')).hexdigest()
             '4f37e5dc9d38391db1728048344c3ab5ff8cecb2'])

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'ubuntu.png'))
    def test_cache_filled_on_miss(self):
        # When the cache is empty, downloading an avatar from a given url
        # fills the cache with the image data.
        with mock.patch('friends.utils.avatar.CACHE_DIR',
                        self._avatar_cache) as cache_dir:
            # The file has not yet been downloaded because the directory does
            # not yet exist.  It is created on demand.
            self.assertFalse(os.path.isdir(cache_dir))
            os.makedirs(cache_dir)
            Avatar.get_image('http://example.com')
            # Soup.Message() was called once.  Get the mock and check it.
            from friends.utils.http import Soup
            self.assertEqual(Soup.Message.call_count, 1)
            # Now the file is there.
            self.assertEqual(os.listdir(cache_dir),
                            # hashlib.sha1('http://example.com'
                            # .encode('utf-8')).hexdigest()
                            ['89dce6a446a69d6b9bdc01ac75251e4c322bcdff',
                             '89dce6a446a69d6b9bdc01ac75251e4c322bcdff.100px'])

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'ubuntu.png'))
    def test_cache_used_on_hit(self):
        # When the cache already contains the file, it is not downloaded.
        with mock.patch('friends.utils.avatar.CACHE_DIR',
                        self._avatar_cache) as cache_dir:
            os.makedirs(cache_dir)
            src = resource_filename('friends.tests.data', 'ubuntu.png')
            dst = os.path.join(
                cache_dir, '89dce6a446a69d6b9bdc01ac75251e4c322bcdff')
            shutil.copyfile(src, dst)
            # Get the image, resulting in a cache hit.
            path = Avatar.get_image('http://example.com')
            # No download occurred.  Check the mock.
            from friends.utils.http import Soup
            self.assertEqual(Soup.Message.call_count, 0)
        # Confirm that the resulting cache image is actually a PNG.
        with open(path, 'rb') as raw:
            # This is the PNG file format magic number, living in the first 8
            # bytes of the file.
            self.assertEqual(raw.read(8), bytes.fromhex('89504E470D0A1A0A'))

    @mock.patch('friends.utils.http.Soup.Message',
                FakeSoupMessage('friends.tests.data', 'ubuntu.png'))
    def test_cache_file_contains_image(self):
        # The image is preserved in the cache file.
        with mock.patch('friends.utils.avatar.CACHE_DIR',
                        self._avatar_cache) as cache_dir:
            os.makedirs(cache_dir)
            path = Avatar.get_image('http://example.com')
        # The image must have been downloaded at least once.
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        self.assertEqual(pixbuf.get_height(), 285)
        self.assertEqual(pixbuf.get_width(), 285)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path + '.100px')
        self.assertEqual(pixbuf.get_height(), 100)
        self.assertEqual(pixbuf.get_width(), 100)
        # Confirm that the resulting cache image is actually a PNG.
        with open(path, 'rb') as raw:
            # This is the PNG file format magic number, living in the first 8
            # bytes of the file.
            self.assertEqual(raw.read(8), bytes.fromhex('89504E470D0A1A0A'))

    def test_cache_expiration(self):
        # Cache files which are more than 4 weeks old get expired.
        #
        # Start by copying two copies of ubuntu.png to the temporary cache
        # dir.  Fiddle with their mtimes. so that one is just younger than 4
        # weeks old and one is just older than 4 weeks old.  Run the cache
        # eviction method and ensure that the young one is retained while the
        # old one is removed.
        with mock.patch('friends.utils.avatar.CACHE_DIR',
                        self._avatar_cache) as cache_dir:
            os.makedirs(cache_dir)
            src = resource_filename('friends.tests.data', 'ubuntu.png')
            aaa = os.path.join(cache_dir, 'aaa')
            shutil.copyfile(src, aaa)
            bbb = os.path.join(cache_dir, 'bbb')
            shutil.copyfile(src, bbb)
            # Leave the atime unchanged.
            four_weeks_ago = date.today() - timedelta(weeks=4)
            young = four_weeks_ago + timedelta(days=1)
            old = four_weeks_ago - timedelta(days=1)
            # aaa will be young enough to keep (i.e. 4 weeks less one day ago)
            os.utime(aaa,
                     (os.stat(aaa).st_atime, time.mktime(young.timetuple())))
            # bbb will be too old to keep (i.e. 4 weeks plus one day ago)
            os.utime(bbb,
                     (os.stat(bbb).st_atime, time.mktime(old.timetuple())))
            Avatar.expire_old_avatars()
            self.assertEqual(os.listdir(cache_dir), ['aaa'])
