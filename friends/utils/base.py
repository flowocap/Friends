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

"""Protocol base class and manager."""


__all__ = [
    'Base',
    'feature',
    'initialize_caches',
    ]


import re
import time
import string
import logging
import threading

from datetime import datetime
from oauthlib.oauth1 import Client

from gi.repository import GLib, GObject, EDataServer, EBook

from friends.errors import FriendsError, ContactsError
from friends.utils.authentication import Authentication
from friends.utils.model import COLUMN_INDICES, SCHEMA, DEFAULTS
from friends.utils.model import Model, persist_model
from friends.utils.notify import notify
from friends.utils.time import ISO8601_FORMAT


STUB = lambda *ignore, **kwignore: None
IGNORED = string.punctuation + string.whitespace
SCHEME_RE = re.compile('http[s]?://|friends:/', re.IGNORECASE)
EMPTY_STRING = ''
COMMA_SPACE = ', '
AVATAR_IDX = COLUMN_INDICES['icon_uri']
FROM_ME_IDX = COLUMN_INDICES['from_me']
STREAM_IDX = COLUMN_INDICES['stream']
SENDER_IDX = COLUMN_INDICES['sender']
MESSAGE_IDX = COLUMN_INDICES['message']
IDS_IDX = COLUMN_INDICES['message_ids']
TIME_IDX = COLUMN_INDICES['timestamp']


# This is a mapping from Dee.SharedModel row keys to the DeeModelIters
# representing the rows matching those keys.  It is used for quickly finding
# duplicates when we want to insert new rows into the model.
_seen_messages = {}
_seen_ids = {}


# Protocol __call__() methods run in threads, so we need to serialize
# publishing new data into the SharedModel.
_publish_lock = threading.Lock()

# Avoid race condition during shut-down
_exit_lock = threading.Lock()


log = logging.getLogger(__name__)


def feature(method):
    """Decorator for marking a method as a public feature.

    Use like so:

    @feature
    def method(self):
        # ...

    Then find all feature methods for a protocol with:

    for feature_name in ProtocolClass.get_features():
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
    (pretend that we support G+ for a moment).  Fred writes 'Hey jimbob, been
    to http://example.com lately?', and this message might show up on Twitter
    like 'Hey @jimbob, been to example.com lately?', but it might show up on
    G+ like 'Hey +jimbob, been to http://example.com lately?'.  So we need to
    strip out all the possibly different bits in order to identify that these
    messages are the same for our purposes.  In both of these cases, the
    string is converted into 'Heyjimbobbeentoexamplecomlately' and then they
    compare equally, so we've identified a duplicate message.
    """
    # Given a 'row' of data, the sender and message fields are concatenated
    # together to form the raw key.  Then we strip out details such as url
    # schemes, punctuation, and whitespace, that allow for the fuzzy matching.
    key = SCHEME_RE.sub('', row[SENDER_IDX] + row[MESSAGE_IDX])
    # Now remove all punctuation and whitespace.
    return EMPTY_STRING.join([char for char in key if char not in IGNORED])


def initialize_caches():
    """Populate _seen_ids and _seen_messages with Model data.

    Our Dee.SharedModel persists across instances, so we need to
    populate these caches at launch.
    """
    for i in range(Model.get_n_rows()):
        row_iter = Model.get_iter_at_row(i)
        row = Model.get_row(row_iter)
        _seen_messages[_make_key(row)] = i
        for triple in row[IDS_IDX]:
            _seen_ids[tuple(triple)] = i
    log.debug(
        '_seen_ids: {}, _seen_messages: {}'.format(
            len(_seen_ids), len(_seen_messages)))


class _OperationThread(threading.Thread):
    """Manage async callbacks, and log subthread exceptions."""
    # main.py will replace this with a reference to the mainloop.quit method
    shutdown = lambda: log.error('Failed to exit friends-dispatcher main loop')

    def __init__(self, *args, id=None, success=STUB, failure=STUB, **kws):
        self._id = id
        self._success_callback = success
        self._failure_callback = failure

        # Wrap the real target inside retval_catcher
        method = kws.get('target')
        kws['args'] = (method,) + kws.get('args', ())
        kws['target'] = self._retval_catcher

        super().__init__(*args, **kws)

    def _retval_catcher(self, func, *args, **kwargs):
        """Call the success callback, but only if no exceptions were raised."""
        self._success_callback(str(func(*args, **kwargs)))

    def run(self):
        log.debug('{} is starting in a new thread.'.format(self._id))
        start = time.time()
        try:
            super().run()
        except Exception as err:
            # Raising an exception is the only way for a protocol
            # operation to avoid triggering the success callback.
            self._failure_callback(str(err))
            log.exception(err)
        elapsed = time.time() - start
        log.debug('{} has completed in {:.2f}s, thread exiting.'.format(
                self._id, elapsed))

        # If this is the last thread to exit, then the refresh is
        # completed and we should save the model, and then exit.
        with _exit_lock:
            if threading.activeCount() < 3:
                persist_model()
                GLib.idle_add(self.shutdown)


class Base:
    """Parent class for any protocol plugin such as Facebook or Twitter.

    In order to add support for a new social network (hereafter
    referred to as a "protocol") to Friends, you must first ensure
    that Ubuntu Online Accounts supports your protocol, then create a
    new class that subclasses this one, and then override as many
    methods as necessary until your protocol functions as desired.
    Please refer to protocols/facebook.py and protocols/twitter.py for
    relatively complete examples of how to do this.

    This documentation will identify which methods are necessary to
    override in order to build a working protocol plugin. If you find
    that some of the code in this class is not actually compatible
    with the protocol you are trying to implement, it should be
    straightforward to override it, however this should be unlikely.
    The code in this class has been tested against Facebook, Twitter,
    Flickr, Identica, and Foursquare, and works well with all of them.
    """
    # Used for EDS stuff.
    _source_registry = None

    # This number serves a guideline (not a hard limit) for the protocol
    # subclasses to download in each refresh.
    _DOWNLOAD_LIMIT = 50

    # Default to not notify any messages. This gets overridden from main.py,
    # which is the only place we can safely access gsettings from.
    _do_notify = lambda protocol, stream: False

    def __init__(self, account):
        self._account = account

    def _whoami(self, result):
        """Use OAuth login results to identify the authenticating user.

        This method gets called with the OAuth server's login
        response, and must be used to populate self._account.user_id
        and self._account.user_name variables. Each protocol must
        override this method to accomplish this task specifically for
        the social network being implemented. For example, Twitter
        provides this information directly and simply needs to be
        assigned to the variables; Facebook does not provide this
        information and thus it's necessary to initiate an additional
        HTTP request within this method in order to discover that
        information.

        This method will be called only once, immediately after a
        successful OAuth authentication, and you can safely assume
        that self._account.access_token will already be populated with
        a valid access token by the time this method is invoked.

        :param result: An already-instantiated JSON object, typically in the
            form of a dict, typically containing an AccessToken key and
            potentially others.
        :type result: dict
        """
        raise NotImplementedError(
            '{} protocol has no _whoami() method.'.format(
                self.__class__.__name__))

    def receive(self):
        """Poll the social network for new messages.

        Friends will periodically invoke this method on your protocol
        in order to fetch new messages and publish them into the
        Dee.SharedModel.

        This method must be implemented by all subclasses. It is
        expected to initiate an HTTP request to the social network,
        interpret the results, and then call self._publish() with the
        interpreted results.

        Typically, this method (and other similar ones that you may
        implement at your option) will start with a call to
        self._get_access_token(), as this is the recommended way to
        initiate only a single login attempt (all subsequent calls
        return the cached access token without re-authenticating).

        The Friends-dispatcher will invoke these methods
        asynchronously, in a sub-thread, but we have designed the
        threading architecture in a very orthogonal way, so it should
        be very easy for you to write the methods in a straightforward
        synchronous way. If you need to indicate that there is an
        error condition (any error condition at all), just raise an
        exception (any exception will do, as long as it is a subclass
        of the builtin Exception class). Friends-dispatcher will
        automatically log the exception and indicate the error
        condition to the user. If you need to return a value (such as
        the destination URL that a successfully uploaded photo has
        been uploaded to), you can simply return the value, and
        Friends-dispatcher will catch that return value and invoke a
        callback in the calling code for you automatically. Only a
        single return value is supported, and it must be converted
        into a string to be sent over DBus.
        """
        raise NotImplementedError(
            '{} protocol has no receive() method.'.format(
                self.__class__.__name__))

    def __call__(self, operation, *args, success=STUB, failure=STUB, **kwargs):
        """Call an operation, i.e. a method, with arguments in a sub-thread.

        If a protocol method raises an exception, that will be caught
        and passed to the failure callback; if no exception is raised,
        then the return value of the method will be passed to the
        success callback. Programs communicating with friends-dispatcher
        via DBus should therefore specify success & failure callbacks
        in order to be notified of the results of their DBus method
        calls.

        :param operation: The name of the instance method to invoke in
            a sub-thread.
        :type operation: string
        :param args: The arguments you wish to pass to that method.
        :type args: tuple
        :param kwargs: Keyword arguments you wish to pass to that method.
        :type kwargs: dict
        :param success: A callback to invoke in the event of successful
            asynchronous completion.
        :type success: callable
        :param failure: A callback to invoke in the event of an exception being
            raised in the sub-thread.
        :type failure: callable
        :return: None
        """
        if operation.startswith('_') or not hasattr(self, operation):
            raise NotImplementedError(operation)
        method = getattr(self, operation)
        _OperationThread(
            id='{}.{}'.format(self.__class__.__name__, operation),
            target=method,
            success=success,
            failure=failure,
            args=args,
            kwargs=kwargs,
            ).start()

    def _get_n_rows(self):
        """Return the number of rows in the Dee.SharedModel."""
        return len(Model)

    def _publish(self, message_id, **kwargs):
        """Publish fresh data into the model, ignoring duplicates.

        This method inserts a new full row into the Dee.SharedModel
        that we use for storing and sharing tweets/messages/posts/etc.

        Rows cannot (easily) be modified once inserted, so if you need
        to process a lot of information in order to construct a row,
        it is easiest to invoke this method like so:

            args = {}
            args['message_id'] = '1234'
            args['message'] = 'hello.'
            args['from_me'] = is_from_me() #etc
            self._publish(**args)

        :param message_id: The service-specific id of the message being
            published.  Serves as the third component of the unique
            'message_ids' column.
        :type message_id: string
        :param kwargs: The additional column name/values to be published into
            the model.  Not all columns must be given, but it is an error if
            any non-column keys are given. Refer to utils/model.py to see the
            schema which defines the valid arguments to this method.
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
            row_idx = _seen_messages.get(key)
            if row_idx is None:
                # We haven't seen this message before.
                _seen_messages[key] = Model.get_position(Model.append(*args))
                # I think it's safe not to notify the user about
                # messages that they sent themselves...
                if not args[FROM_ME_IDX] and self._do_notify(args[STREAM_IDX]):
                    notify(
                        args[SENDER_IDX],
                        args[MESSAGE_IDX],
                        args[AVATAR_IDX],
                        )
            else:
                # We have seen this before, so append to the matching column's
                # message_ids list, this message's id.
                row = Model.get_row(Model.get_iter_at_row(row_idx))
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
        """Remove message_id from the Dee.SharedModel.

        :param message_id: The service-specific id of the message being
            published.
        :type message_id: string
        """
        triple = (self.__class__.__name__.lower(),
                  self._account.id,
                  message_id)
        log.debug('Unpublishing {}!'.format(triple))

        row_idx = _seen_ids.pop(triple, None)
        if row_idx is None:
            raise FriendsError('Tried to delete an invalid message id.')

        row_iter = Model.get_iter_at_row(row_idx)
        row = Model.get_row(row_iter)

        if len(row[IDS_IDX]) == 1:
            # Message only exists on one protocol, delete it
            del _seen_messages[_make_key(row)]
            Model.remove(row_iter)
            # Shift our cached indexes up one, when one gets deleted.
            for key, value in _seen_ids.items():
                if value > row_idx:
                    _seen_ids[key] = value - 1
        else:
            # Message exists on other protocols too, only drop id
            row[IDS_IDX] = [ids for ids
                            in row[IDS_IDX]
                            if ids[-1] != message_id]

    def _unpublish_all(self):
        """Remove all of this account's messages from the Model.

        Saves the Model to disk after it is done purging rows."""
        for triple in _seen_ids.copy():
            if self._account.id in triple:
                self._unpublish(triple[-1])
        persist_model()

    def _get_access_token(self):
        """Return an access token, logging in if necessary.

        :return: The access_token, if we are successfully logged in."""
        if self._account.access_token is None:
            self._login()

        return self._account.access_token

    def _login(self):
        """Prevent redundant login attempts.

        This method implements some tricky threading logic in order to
        avoid race conditions, and it should not be overridden any
        subclass. If you need to modify the way logging in functions
        in order to make your protocol login correctly, you should
        override _locked_login() instead.

        :return: True if we are already logged in, or if a new login
            was successful.
        """
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
        """Synchronous login implementation.

        Subclasses should only need to implement _whoami() in order to
        handle the protocol-specific details of a login operation,
        however this method can be overridden if you need a greater
        degree of control over the login process. It is safe to assume
        that this method will only be called once, the first time any
        subthread needs to log in. You do not have to worry about
        subthread race conditions inside this method.
        """
        protocol = self.__class__.__name__
        log.debug('{} to {}'.format(
                'Re-authenticating' if old_token else 'Logging in', protocol))

        result = Authentication(self._account).login()

        self._account.access_token = result.get('AccessToken')
        self._whoami(result)
        log.debug('{} UID: {}'.format(protocol, self._account.user_id))

    def _get_oauth_headers(self, method, url, data=None, headers=None):
        """Basic wrapper around oauthlib that we use for Twitter and Flickr."""
        # "Client" == "Consumer" in oauthlib parlance.
        client_key = self._account.auth.parameters['ConsumerKey']
        client_secret = self._account.auth.parameters['ConsumerSecret']

        # "resource_owner" == secret and token.
        resource_owner_key = self._get_access_token()
        resource_owner_secret = self._account.secret_token
        oauth_client = Client(client_key, client_secret,
                              resource_owner_key, resource_owner_secret)

        headers = headers or {}
        if data is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        # All we care about is the headers, which will contain the
        # Authorization header necessary to satisfy OAuth.
        uri, headers, body = oauth_client.sign(
            url, body=data, headers=headers or {}, http_method=method)

        return headers

    def _is_error(self, data):
        """Is the return data an error response?"""
        try:
            error = data.get('error') or data.get('errors')
        except AttributeError:
            return False
        if error is None:
            return False
        try:
            message = error.get('message')
        except AttributeError:
            message = None
        raise FriendsError(message or str(error))

    def _new_book_client(self, source):
        client = EBook.BookClient.new(source)
        client.open_sync(False, None)
        return client

    def _push_to_eds(self, online_service, contact):
        source_match = self._get_eds_source(online_service)
        if source_match is None:
            raise ContactsError(
                '{} does not have an address book.'.format(
                    online_service))
        client = self._new_book_client(source_match)
        success = client.add_contact_sync(contact, None)
        if not success:
            raise ContactsError('Failed to save contact {!r}', contact)

    def _get_eds_source_registry(self):
        if self._source_registry is None:
            self._source_registry = EDataServer.SourceRegistry.new_sync(None)

    def _create_eds_source(self, online_service):
        self._get_eds_source_registry()
        source = EDataServer.Source.new(None, None)
        source.set_display_name(online_service)
        source.set_parent('local-stub')
        extension = source.get_extension(
            EDataServer.SOURCE_EXTENSION_ADDRESS_BOOK)
        extension.set_backend_name('local')
        if self._source_registry.commit_source_sync(source, None):
            # https://bugzilla.gnome.org/show_bug.cgi?id=685986
            # Potential race condition - need to sleep for a
            # couple of cycles to ensure the registry will return
            # a valid source object after commiting. Evolution fix
            # on the way but for now we need this.
            time.sleep(2)
            return self._source_registry.ref_source(source.get_uid())

    def _get_eds_source(self, online_service):
        self._get_eds_source_registry()
        for previous_source in self._source_registry.list_sources(None):
            if previous_source.get_display_name() == online_service:
                return self._source_registry.ref_source(
                    previous_source.get_uid())

    def _previously_stored_contact(self, source, field, search_term):
        client = self._new_book_client(source)
        query = EBook.book_query_vcard_field_test(
            field, EBook.BookQueryTest(0), search_term)
        success, result = client.get_contacts_sync(query.to_string(), None)
        if not success:
            raise ContactsError('Search failed on field {}'.format(field))
        return len(result) > 0

    def _delete_service_contacts(self, source):
        client = self._new_book_client(source)
        query = EBook.book_query_any_field_contains('')
        success, results = client.get_contacts_sync(query.to_string(), None)
        if not success:
            raise ContactsError('Search for delete all contacts failed')
        log.debug('Found {} contacts to delete'.format(len(results)))
        for contact in results:
            log.debug(
                'Deleting contact {}'.format(
                    contact.get_property('full-name')))
            client.remove_contact_sync(contact, None)
        return True

    def _create_contact(self, user_fullname, user_nickname,
                        social_network_attrs):
        """Build a VCard based on a dict representation of a contact."""
        vcard = EBook.VCard.new()
        info = social_network_attrs

        for i in info:
            attr = EBook.VCardAttribute.new('social-networking-attributes', i)
            if type(info[i]) == type(dict()):
                for j in info[i]:
                    param = EBook.VCardAttributeParam.new(j)
                    param.add_value(info[i][j])
                    attr.add_param(param);
            else:
                attr.add_value(info[i])
            vcard.add_attribute(attr)

        contact = EBook.Contact.new_from_vcard(
            vcard.to_string(EBook.VCardFormat(1)))
        contact.set_property('full-name', user_fullname)
        if user_nickname is not None:
            contact.set_property('nickname', user_nickname)

        log.debug('Creating new contact for {}'.format(user_fullname))
        return contact

    @classmethod
    def get_features(cls):
        """Report what public operations we expose over DBus."""
        features = []
        for name in dir(cls):
            if getattr(getattr(cls, name), 'is_feature', False):
                features.append(name)
        return sorted(features)
