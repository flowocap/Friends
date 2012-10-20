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

"""Protocol base class and manager."""


__all__ = [
    'Base',
    'feature',
    ]


import re
import string
import logging
import threading

from friends.utils.authentication import Authentication
from friends.utils.model import COLUMN_INDICES, SCHEMA, DEFAULTS, Model


IGNORED = string.punctuation + string.whitespace
SCHEME_RE = re.compile('http[s]?://|friends:/', re.IGNORECASE)
EMPTY_STRING = ''
COMMA_SPACE = ', '
SENDER_IDX = COLUMN_INDICES['sender']
MESSAGE_IDX = COLUMN_INDICES['message']
IDS_IDX = COLUMN_INDICES['message_ids']


# This is a mapping from Dee.SharedModel row keys to the DeeModelIters
# representing the rows matching those keys.  It is used for quickly finding
# duplicates when we want to insert new rows into the model.
_seen_messages = {}
_seen_ids = {}


# Protocol __call__() methods run in threads, so we need to serialize
# publishing new data into the SharedModel.
_publish_lock = threading.Lock()


log = logging.getLogger(__name__)


def feature(method):
    """Decorator for marking a method as a public feature.

    Use like so:

    @feature
    def method(self):
        # ...

    Then find all feature methods for a protocol with:

    for feature_name in ProtocolClass.features:
        # ...
    """
    method.is_feature = True
    return method


def _make_key(row):
    """Return a unique key for a row in the model.

    This is used for fuzzy comparisons with messages that are already in the
    model.  We don't want duplicate messages to show up in the stream of
    messages that are visible to the user.  But different social media sites
    attach different semantic meanings to different punctuation marks, so we
    want to ignore those for the sake of determining whether one message is
    actually identical to another or not.  Thus, we need to strip out this
    punctuation for the sake of comparing the strings.  For example:

    Fred uses Friends to post identical messages on Twitter and Google+
    (pretend that we support G+ for a moment).  Fred writes "Hey jimbob, been
    to http://example.com lately?", and this message might show up on Twitter
    like "Hey @jimbob, been to example.com lately?", but it might show up on
    G+ like "Hey +jimbob, been to http://example.com lately?".  So we need to
    strip out all the possibly different bits in order to identify that these
    messages are the same for our purposes.  In both of these cases, the
    string is converted into "Heyjimbobbeentoexamplecomlately" and then they
    compare equally, so we've identified a duplicate message.
    """
    # Given a "row" of data, the sender and message fields are concatenated
    # together to form the raw key.  Then we strip out details such as url
    # schemes, punctuation, and whitespace, that allow for the fuzzy matching.
    key = SCHEME_RE.sub('', row[SENDER_IDX] + row[MESSAGE_IDX])
    # Now remove all punctuation and whitespace.
    return EMPTY_STRING.join(char for char in key if char not in IGNORED)


def _initialize_caches():
    """Populate _seen_ids and _seen_messages with Model data.

    Our Dee.SharedModel persists across instances, so we need to
    populate these caches at launch.
    """
    for i in range(Model.get_n_rows()):
        row_iter = Model.get_iter_at_row(i)
        row = Model.get_row(row_iter)
        _seen_messages[_make_key(row)] = row_iter
        for triple in row[IDS_IDX]:
            _seen_ids[tuple(triple)] = row_iter

_initialize_caches()


class _OperationThread(threading.Thread):
    """Catch, log, and swallow all exceptions in the sub-thread."""

    def __init__(self, barrier, *args, identifier=None, **kws):
        # The barrier will only be provided when the system is under test.
        self._barrier = barrier
        self._id = identifier
        super().__init__(*args, **kws)

    # Always run these as daemon threads, so they don't block the main thread,
    # i.e. friends-service, from exiting.
    daemon = True

    def run(self):
        log.debug('{} is starting in a new thread.'.format(self._id))
        try:
            super().run()
        except Exception:
            log.exception('Friends operation exception:\n')
        log.debug('{} has completed, thread exiting.'.format(self._id))
        # If the system is under test, indicate that we've reached the
        # barrier, so that the main thread, i.e. the test thread waiting for
        # the results, can then proceed.
        if self._barrier is not None:
            self._barrier.wait()


class Base:
    # This number serves a guideline (not a hard limit) for the protocol
    # subclasses to download in each refresh.
    _DOWNLOAD_LIMIT = 50
    # When the system is under test, set this value to True to enable
    # synchronizing the operations threads with the main thread.  In this way,
    # you can ensure that the results of calling an operation on a protocol
    # will complete before the assertions testing the results of that
    # operation.
    _SYNCHRONIZE = False

    def __init__(self, account):
        self._account = account

    def __call__(self, operation, *args, **kwargs):
        """Call an operation, i.e. a method, with arguments in a sub-thread.

        Sub-threads do not currently communicate any state to the main thread,
        and any exception that occurs in the sub-thread is simply logged and
        discarded.
        """
        if operation.startswith('_') or not hasattr(self, operation):
            raise NotImplementedError(operation)
        method = getattr(self, operation)
        # When the system is under test, or at least tests which assert the
        # results of operations in a sub-thread, then this flag will be set to
        # true, in which case we want to pass a barrier to the sub-thread.
        # The sub-thread will complete, either successfully or unsuccessfully,
        # but in either case, it will always indicate that it's reached the
        # barrier before exiting.  The main thread, i.e. this one, will not
        # proceed until that barrier has been reached, thus allowing the main
        # thread to assert the results of the sub-thread.
        barrier = (threading.Barrier(parties=2) if Base._SYNCHRONIZE else None)
        _OperationThread(barrier,
                         identifier='{}.{}'.format(self.__class__.__name__,
                                                   operation),
                         target=method, args=args, kwargs=kwargs).start()
        # When under synchronous testing, wait until the sub-thread completes
        # before returning.
        if barrier is not None:
            barrier.wait()

    def _publish(self, message_id, **kwargs):
        """Publish fresh data into the model, ignoring duplicates.

        :param message_id: The service-specific id of the message being
            published.  Serves as the third component of the unique
            'message_ids' column.
        :type message_id: string
        :param kwargs: The additional column name/values to be published into
            the model.  Not all columns must be given, but it is an error if
            any non-column keys are given.
        :raises: TypeError if non-column names are given in kwargs.
        :return: True if the message was appended to the model or already
            present.  Otherwise, False is returned if the message could not be
            appended.
        """
        # Initialize the row of arguments to contain the message_ids value.
        # The column value is a list of lists (see friends/utils/model.py for
        # details), and because the arguments are themselves a list, this gets
        # initialized as a triply-nested list.
        triple = [self.__class__.__name__.lower(),
                  self._account.id,
                  message_id]
        args = [[triple]]
        # Now iterate through all the column names listed in the SCHEMA,
        # except for the first, since we just composed its value in the
        # preceding line.  Pop matching column values from the kwargs, in the
        # order which they appear in the SCHEMA.  If any are left over at the
        # end of this, raise a TypeError indicating the unexpected column
        # names.
        #
        # Missing column values default to the empty string.
        for column_name, column_type in SCHEMA[1:]:
            args.append(kwargs.pop(column_name, DEFAULTS[column_type]))
        if len(kwargs) > 0:
            raise TypeError('Unexpected keyword arguments: {}'.format(
                COMMA_SPACE.join(sorted(kwargs))))
        with _publish_lock:
            # Don't let duplicate messages into the model, but do record the
            # unique message ids of each duplicate message.
            key = _make_key(args)
            row_iter = _seen_messages.get(key)
            if row_iter is None:
                # We haven't seen this message before.
                _seen_messages[key] = Model.append(*args)
            else:
                # We have seen this before, so append to the matching column's
                # message_ids list, this message's id.
                row = Model.get_row(row_iter)
                # Remember that row[IDS] is the nested list-of-lists of
                # message_ids.  args[IDS] is the nested list-of-lists for the
                # message that we're publishing.  The outer list of the latter
                # will always be of size 1.  We want to take the inner list
                # from args and append it to the list-of-lists (i.e.
                # message_ids) of the row already in the model.  To make sure
                # the model gets updated, we need to insert into the row, thus
                # it's best to concatenate the two lists together and store it
                # back into the column.
                if triple not in row[IDS_IDX]:
                    row[IDS_IDX] = row[IDS_IDX] + args[IDS_IDX]
            # Tuple-ize triple because lists, being mutable, cannot be used as
            # dictionary keys.
            _seen_ids[tuple(triple)] = _seen_messages.get(key)
            return key in _seen_messages

    def _unpublish(self, message_id):
        """Remove message_id from the Dee.SharedModel."""
        triple = (self.__class__.__name__.lower(),
                  self._account.id,
                  message_id)

        row_iter = _seen_ids.pop(triple, None)
        if row_iter is None:
            log.error('Tried to delete an invalid message id.')
            return

        row = Model.get_row(row_iter)
        if len(row[IDS_IDX]) == 1:
            # Message only exists on one protocol, delete it
            del _seen_messages[_make_key(row)]
            Model.remove(row_iter)
        else:
            # Message exists on other protocols too, only drop id
            row[IDS_IDX] = [ids for ids
                            in row[IDS_IDX]
                            if message_id not in ids]

    def _get_access_token(self):
        """Return an access token, logging in if necessary."""
        if self._account.access_token is None:
            if not self._login():
                log.error(
                    'No {} authentication results received.'.format(
                        self.__class__.__name__))
                return None
        return self._account.access_token

    def _login(self):
        """Prevent redundant login attempts."""
        # The first time the user logs in, we expect old_token to be None.
        # Because this code can be executed in multiple threads, we first
        # acquire a lock and then try to log in.  The act of logging in also
        # sets an access token.  This is all part of the libaccounts API.
        #
        # The check of the access token prevents the following race condition:
        # + Thread A sees no access token so it is not logged in.
        # + Thread B sees no access token so it is not logged in.
        # + Thread A and B both try to acquire the login lock, and A wins
        # + Thread A sees that the access token has not changed, so it knows
        #   that it won the race.  It logs in, getting a new, different access
        #   token.  Since that does not match the pre-lock token, thread A
        #   returns True.
        # + As Thread A is returning, it releases the lock (*after* it's
        #   calculated the return value).
        # + Thread B acquires the lock and sees that the access token has
        #   changed because thread A is already logged in.  It does not try to
        #   log in again, but also returns True since the access token has
        #   changed.  IOW, thread B is also already logged in via thread A.
        old_token = self._account.access_token
        with self._account.login_lock:
            if self._account.access_token == old_token:
                self._locked_login(old_token)
            # This test must be performed while the login lock is acquired,
            # otherwise it's possible for another thread to come in between
            # the release of the login lock and the test, and change the
            # access token.
            return self._account.access_token != old_token

    def _locked_login(self, old_token):
        """Sign in without worrying about concurrent login attempts."""
        protocol = self.__class__.__name__
        log.debug('{} to {}'.format(
                'Re-authenticating' if old_token else 'Logging in', protocol))

        result = Authentication(self._account).login()
        if result is None:
            log.error(
                'No {} authentication results received.'.format(protocol))
            return

        token = result.get('AccessToken')
        if token is None:
            log.error('No AccessToken in {} session: {!r}'.format(
                protocol, result))
        else:
            self._account.access_token = token
            self._whoami(result)
            log.debug('{} UID: {}'.format(protocol, self._account.user_id))

    @classmethod
    def get_features(cls):
        """Report what public operations we expose over DBus."""
        features = []
        for name in dir(cls):
            if getattr(getattr(cls, name), 'is_feature', False):
                features.append(name)
        return sorted(features)
