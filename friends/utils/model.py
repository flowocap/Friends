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

"""The Dee.SharedModel interface layer.

Dee.SharedModel is comparable to a Gtk.ListStore, except that it shares its
state between processes using DBus.  When friends-service downloads new
messages from a website, it inserts those messages into this SharedModel
instance, which then triggers a callback in the Vala frontend, which knows to
display the new messages there.
"""


__all__ = [
    'Model',
    'COLUMN_NAMES',
    'COLUMN_TYPES',
    'COLUMN_INDICES',
    'DEFAULTS',
    ]


from gi.repository import Dee


# Most of this schema is very straightforward, but the 'message_ids' column
# needs a bit of explanation:
#
# It is a two-dimensional array (ie, an array of arrays).  Each inner array
# contains three elements: the name of the protocol (introspected from the
# name of the class that implements the protocol), the account_id (like
# '6/flickr' or '3/facebook'), followed by the message_id for that particular
# service.
#
# Then, there will be one of these triples present for every service on which
# the message exists.  So for example, if the user posts the same message to
# both facebook and twitter, that message will appear as a single row in this
# schema, and the 'message_ids' column will look something like this:
#
# [
#     ['facebook', '2/facebook', '12345'],
#     ['twitter', '3/twitter', '987654'],
# ]
SCHEMA = (
    ('message_ids',    'aas'),
    ('stream',         's'),
    ('sender',         's'),
    ('sender_nick',    's'),
    ('from_me',        'b'),
    ('timestamp',      's'),
    ('message',        's'),
    ('html',           's'),
    ('icon_uri',       's'),
    ('url',            's'),
    ('source',         's'),
    ('reply_nick',     's'),
    ('reply_name',     's'),
    ('reply_url',      's'),
    ('likes',          'd'),
    ('liked',          'b'),
    ('retweet_nick',   's'),
    ('retweet_name',   's'),
    ('retweet_id',     's'),
    ('link_picture',   's'),
    ('link_name',      's'),
    ('link_url',       's'),
    ('link_desc',      's'),
    ('link_caption',   's'),
    ('link_icon',      's'),
    ('img_url',        's'),
    ('img_src',        's'),
    ('img_thumb',      's'),
    ('img_name',       's'),
    ('video_pic',      's'),
    ('video_src',      's'),
    ('video_url',      's'),
    ('video_name',     's'),
    ('comments',       'as'),
    ('recipient',      's'),
    ('recipient_nick', 's'),
    ('recipient_icon', 's'),
    )


# It's useful to have separate lists of the column names and types.
COLUMN_NAMES, COLUMN_TYPES = zip(*SCHEMA)
# A reverse mapping from column name to the column index.  This is useful for
# pulling column values out of a row of data.
COLUMN_INDICES = {name: i for i, name in enumerate(COLUMN_NAMES)}
# This defines default values for the different data types
DEFAULTS = {
    'as': [],
    'b': False,
    's': '',
    'd': 0,
    }


Model = Dee.SharedModel.new('com.canonical.Friends.Streams')
Model.set_schema_full(COLUMN_TYPES)
