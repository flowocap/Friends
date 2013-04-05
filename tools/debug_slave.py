#!/usr/bin/env python3

"""Usage: ./tools/debug_slave.py

Run this script in parallel with debug_live.py to watch changes to the Friends
database model as it is updated over dbus.

It is not intended for use with an installed friends package.
"""

from gi.repository import Dee
from gi.repository import GLib

from friends.tests.mocks import SCHEMA


class Slave:
    def __init__(self):
        model_name = 'com.canonical.Friends.Streams'
        print('Joining model ' + model_name)
        self.model = Dee.SharedModel.new(model_name)
        self.model.connect('row-added', self.on_row_added)
        self.model.connect('row-changed', self.on_row_added)

    def on_row_added(self, model, itr):
        row = self.model.get_row(itr)
        print('\n' * 5)
        for i, col in enumerate(row):
            print('{:12}: {}'.format(SCHEMA.NAMES[i], col))
        print('ROWS: ', len(self.model))


if __name__ == '__main__':
    s = Slave()
    GLib.MainLoop().run()
