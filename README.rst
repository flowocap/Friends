==================
Installing Friends
==================

Requirements
============

Package requirements.

    * gir1.2-dee-1.0
    * gir1.2-gdkpixbuf-2.0
    * gir1.2-glib-2.0
    * gir1.2-networkmanager-1.0
    * gir1.2-signon-1.0
    * gir1.2-soup-2.4
    * gir1.2-soup-gnome-2.4
    * python3 (>= 3.2, although 3.3 will soon be required)
    * python3-distutils-extra
    * python3-dbus
    * gir1.2-ebook-1.2
    * gir1.2-edataserver-1.2
    * python3-mock


Installation
============

If you want to run the ``friends-service`` executable locally for testing
purposes, you can do it in one of two ways.  To run the service as would
typically happen once the system package was installed, create a Python
virtual environment, and run the service from there.  Fortunately, the
``Makefile`` makes this easy::

    $ make venv
    $ /tmp/friends/bin/friends-service

When you make changes in the source, just run ``make venv`` again to refresh
the virtual environment.

It may be easier during development to run the service directly from the
source directory.  This should generally be good enough for development
purposes, but again, doesn't exactly mimic how the service will be installed
by the system package::

    $ ./friends-service.sh

This is a little bit more fragile, since you must be in the top-level source
directory for this to work.

Once the service is running, it will access Ubuntu Online Accounts for all
your microblogging-enabled accounts, and then retrieve all the public messages
present on those accounts.  Those messages can then be accessed over DBus,
using a Dee.SharedModel.


Testing
=======

You can run most of the test suite with the command ``make check``.  This will
not include any dbus-enabled tests, which you can run with the command ``make
check_all``.

You can do some microblogging from the command line with::

    $ ./tools/debug_live.py twitter send 'Hello, World!'
