#!/usr/bin/env python3

"""Usage: ./tools/debug_live.py PROTOCOL OPERATION [OPTIONS]

Where PROTOCOL is a protocol supported by Friends, such as 'twitter',
OPERATION is an instance method defined in that protocol's class, and OPTIONS
are whatever arguments you'd like to pass to that method (if any), such as
message id's or a status message.

Examples:

./tools/debug_live.py twitter home
./tools/debug_live.py twitter send 'Hello, world!'

This tool is provided to aid with rapid feedback of changes made to the
friends source tree, and as such is designed to be run from the same directory
that contains 'setup.py'.

It is not intended for use with an installed friends package.
"""

import sys
import time
import logging

sys.path.insert(0, '.')

from gi.repository import GObject
from friends.utils.logging import initialize
from friends.utils.account import AccountManager
from friends.utils.base import Base
from friends.utils.model import Model

# Print all logs for debugging purposes
initialize(debug=True, console=True)


log = logging.getLogger('friends.debug_live')


def row_added(model, itr):
    row = model.get_row(itr)
    print(row)
    log.info('ROWS: {}'.format(len(model)))
    print()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    protocol = sys.argv[1]
    args = sys.argv[2:]

    found = False
    a = AccountManager(None)

    Model.connect('row-added', row_added)

    for account_id, account in a._accounts.items():
        if account_id.endswith(protocol):
            found = True
            account.protocol(*args)

    if not found:
        log.error('No {} found in Ubuntu Online Accounts!'.format(protocol))
    else:
        loop = GObject.MainLoop()
        GObject.timeout_add_seconds(10, loop.quit)
        loop.run()
