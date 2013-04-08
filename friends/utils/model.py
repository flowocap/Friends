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

"""The Dee.SharedModel interface layer.

Dee.SharedModel is comparable to a Gtk.ListStore, except that it
shares its state between processes using DBus. When friends-dispatcher
downloads new messages from a website, it inserts those messages into
this SharedModel instance, which then triggers a callback in the Vala
frontend, which knows to display the new messages there.
"""


__all__ = [
    'Schema',
    'Model',
    'MODEL_DBUS_NAME',
    'persist_model',
    'prune_model',
    ]


from gi.repository import Dee

import logging
log = logging.getLogger(__name__)


class Schema:
    """Represents the DeeModel schema data that we defined in CSV."""
    DEFAULTS = {
        'b': False,
        's': '',
        'd': 0,
        't': 0,
        }

    FILES = [
        'data/model-schema.csv',
        '/usr/share/friends/model-schema.csv',
        ]

    def __init__(self):
        """Parse CSV from disk."""
        self.COLUMNS = []
        self.NAMES = []
        self.TYPES = []
        self.INDICES = {}

        files = self.FILES[:]
        while files:
            filename = files.pop()
            log.debug('Looking for SCHEMA in {}'.format(filename))
            try:
                with open(filename) as schema:
                    for col in schema:
                        name, variant = col.rstrip().split(',')
                        self.COLUMNS.append((name, variant))
                        self.NAMES.append(name)
                        self.TYPES.append(variant)
                log.debug(
                    'Found {} columns for SCHEMA'.format(len(self.COLUMNS)))
                break
            except IOError:
                pass
        self.INDICES = {name: i for i, name in enumerate(self.NAMES)}


MODEL_DBUS_NAME = 'com.canonical.Friends.Streams'
Model = Dee.SharedModel.new(MODEL_DBUS_NAME)


def persist_model():
    """Write our Dee.SharedModel instance to disk."""
    log.debug('Trying to save Dee.SharedModel with {} rows.'.format(len(Model)))
    if Model is not None and Model.is_synchronized():
        log.debug('Saving Dee.SharedModel with {} rows.'.format(len(Model)))
        Model.flush_revision_queue()


def prune_model(maximum):
    """If there are more than maximum rows, remove the oldest ones."""
    pruned = 0
    while Model.get_n_rows() > maximum:
        Model.remove(Model.get_first_iter())
        pruned += 1

    if pruned:
        log.debug('Deleted {} rows from Dee.SharedModel.'.format(pruned))
        # Delete those messages from disk, too, not just memory.
        persist_model()
