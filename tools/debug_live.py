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

sys.path.insert(0, '.')

from gi.repository import GObject

from friends.utils.account import AccountManager
from friends.utils.base import Base
from friends.utils.model import Model, persist_model


# Ensure synchronous operation of Base.__call__() for easier testing.
Base._SYNCHRONIZE = True


def refresh(account):
    print()
    print('#' * 80)
    print('Performing "{}" operation!'.format(args[0]))
    print('#' * 80)

    account.protocol(*args)
    for row in Model:
        print([col for col in row])
        print()
    print('ROWS: ', len(Model))
    persist_model()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    protocol = sys.argv[1]
    args = sys.argv[2:]

    found = False
    a = AccountManager(None)

    for account_id, account in a._accounts.items():
        if account_id.endswith(protocol):
            found = True
            refresh(account)
            GObject.timeout_add_seconds(300, refresh, account)

    if not found:
        print('No {} account found in your Ubuntu Online Accounts!'.format(
            protocol))
    else:
        GObject.MainLoop().run()
