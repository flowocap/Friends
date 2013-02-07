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

"""Notification logic.

If libnotify is missing, then notify() is a do-nothing stub that
silently ignores all calls.
"""


__all__ = [
    'notify',
    ]


from gi.repository import GObject, GdkPixbuf


# This gets conditionally imported at the end of this file, which
# allows for easier overriding of the following function definition.
Notify = None


def notify(title, message, icon_uri='', pixbuf=None):
    """Display the message along with sender's name and avatar."""
    if not (title and message):
        return

    notification = Notify.Notification.new(
        title, message, 'friends')

    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            icon_uri, 48, 48)
    except GObject.GError:
        pass

    if pixbuf is not None:
        notification.set_icon_from_pixbuf(pixbuf)

    if _notify_can_append:
        notification.set_hint_string('x-canonical-append', 'allowed')

    try:
        notification.show()
    except GObject.GError:
        # Most likely we've spammed more than 50 notificatons,
        # not much we can do about that.
        pass

# Optional dependency on Notify library.
try:
    from gi.repository import Notify
except ImportError:
    notify = lambda *ignore, **kwignore: None
else:
    Notify.init('friends')
    _notify_can_append = 'x-canonical-append' in Notify.get_server_caps()
