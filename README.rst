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


Installation
============

Friends uses Python's distutils framework for installation.  In order to
install Friends, you will need to perform the following command as root::

    # make install


Run Friends
===========

Once Friends is installed, you can launch it with the command
``friends-service``.  Once it is running, it will access Ubuntu Online
Accounts for all your microblogging-enabled accounts, and then retrieve all
the public messages present on those accounts.  Those messages can then be
accessed over DBus, using a Dee.SharedModel.


Testing
=======

You can run most of the test suite with the command ``make check``.  This will
not include any dbus-enabled tests, which you can run with the command ``make
check_all``.

You can do some microblogging from the command line with::

    $ ./tools/debug_live.py twitter send 'Hello, World!'