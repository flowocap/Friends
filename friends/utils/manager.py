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
    'ProtocolManager',
    'protocol_manager',
    ]


import os
import importlib

from pkg_resources import resource_listdir

from friends.utils.base import Base


class ProtocolManager:
    """Discover all protocol classes."""

    def __init__(self):
        self.protocols = dict((cls.__name__.lower(), cls)
                              for cls in self._protocol_classes)

    @property
    def _protocol_classes(self):
        """Search for and return all protocol classes."""
        for filename in resource_listdir('friends', 'protocols'):
            basename, extension = os.path.splitext(filename)
            if extension != '.py':
                continue
            module_path = 'friends.protocols.' + basename
            module = importlib.import_module(module_path)
            # Scan all the objects in the module's __all__ and add any which
            # are subclasses of the base protocol class.  Essentially skip any
            # modules that don't have an __all__ (e.g. the __init__.py).
            # However, the module better not lie about its __all__ members.
            for name in getattr(module, '__all__', []):
                obj = getattr(module, name)
                if issubclass(obj, Base):
                    yield obj


protocol_manager = ProtocolManager()
