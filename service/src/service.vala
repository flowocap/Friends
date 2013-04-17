/*
 * Copyright (C) 2013 Canonical Ltd.
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License version 3, as published
 * by the Free Software Foundation.

 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranties of
 * MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
 * PURPOSE.    See the GNU General Public License for more details.

 * You should have received a copy of the GNU General Public License along
 * with this program.    If not, see <http://www.gnu.org/licenses/>.
 *
 * Authored by Ken VanDine <ken.vandine@canonical.com>
 */

using Ag;

[DBus (name = "com.canonical.Friends.Dispatcher")]
private interface Dispatcher : GLib.Object {
        public abstract void Refresh () throws GLib.IOError;
        public abstract void ExpireAvatars () throws GLib.IOError;
        public abstract async void Do (
            string action,
            string account_id,
            string message_id,
            out string result
            ) throws GLib.IOError;
}

[DBus (name = "com.canonical.Friends.Service")]
public class Master : Object
{
    private Dee.Model model;
    private Dee.SharedModel shared_model;
    private unowned Dee.ResourceManager resources;
    private Ag.Manager acct_manager;
    private Dispatcher dispatcher;
    public int interval { get; set; }

    public Master ()
    {
        acct_manager = new Ag.Manager.for_service_type ("microblogging");
        acct_manager.account_deleted.connect ((manager, account_id) => {
                debug ("Account %u deleted from UOA, purging...", account_id);
                uint purged = 0;
                uint rows = model.get_n_rows ();
                // Destructively iterate over the Model from back to
                // front; I know "i < rows" looks kinda goofy here,
                // but what's happening is that i is unsigned, so once
                // it hits 0, i-- will overflow to a very large
                // number, and then "i < rows" will fail, stopping the
                // iteration at index 0.
                for (uint i = rows - 1; i < rows; i--) {
                    var itr = model.get_iter_at_row (i);
                    if (model.get_uint64 (itr, 1) == account_id) {
                        model.remove (itr);
                        purged++;
                    }
                }
                debug ("Purged %u rows.", purged);
            }
        );
        acct_manager.account_created.connect ((manager, account_id) => {
                debug ("Account %u created from UOA, refreshing", account_id);
                try {
                    dispatcher.Refresh ();
                } catch (IOError e) {
                    warning ("Failed to refresh - %s", e.message);
                }
            }
        );

        resources = Dee.ResourceManager.get_default ();
        model = new Dee.SequenceModel ();
        Dee.SequenceModel? _m = null;

        try {
            _m = resources.load ("com.canonical.Friends.Streams") as Dee.SequenceModel;
        } catch (Error e) {
            debug ("Failed to load model from resource manager: %s", e.message);
        }

        string[] SCHEMA = {};

        var file = FileStream.open("/usr/share/friends/model-schema.csv", "r");
        string line = null;
        while (true)
        {
            line = file.read_line();
            if (line == null) break;
            SCHEMA += line.split(",")[1];
        }
        debug ("Found %u schema columns.", SCHEMA.length);

        bool schemaReset = false;

        if (_m is Dee.Model && !schemaReset)
        {
            debug ("Got a valid model");
            // Compare columns from cached model's schema
            string[] _SCHEMA = _m.get_schema ();
            if (_SCHEMA.length != SCHEMA.length)
                schemaReset = true;
            else
            {
                for (int i=0; i < _SCHEMA.length; i++)
                {
                    if (_SCHEMA[i] != SCHEMA[i])
                    {
                        debug ("SCHEMA MISMATCH");
                        schemaReset = true;
                    }
                }
            }
            if (!schemaReset)
                model = _m;
            else
            {
                debug ("Setting schema");
                model.set_schema_full (SCHEMA);
            }
        } else {
            debug ("Setting schema for a new model");
            model.set_schema_full (SCHEMA);
        }

        if (model is Dee.Model)
        {
            debug ("Model with %u rows", model.get_n_rows());

            Dee.Peer peer = Object.new (typeof(Dee.Peer),
                       swarm_name: "com.canonical.Friends.Streams",
                       swarm_owner: true,
                       null) as Dee.Peer;


            peer.peer_found.connect((peername) => {
                debug ("new peer: %s", peername);
            });
            peer.peer_lost.connect((peername) => {
                debug ("lost peer: %s", peername);
            });

            Dee.SharedModel shared_model = Object.new (typeof(Dee.SharedModel),
                       peer: peer,
                       back_end: model,
                       null) as Dee.SharedModel;

            debug ("swarm leader: %s", peer.get_swarm_leader());

            shared_model.notify["synchronized"].connect(() => {
                if (shared_model.is_synchronized()) {
                    debug ("SYNCHRONIZED");
                    shared_model.flush_revision_queue();
                }
                if (shared_model.is_leader())
                    debug ("LEADER");
                else
                    debug ("NOT LEADER");
            });

            Timeout.add_seconds (300, () => {
                shared_model.flush_revision_queue();
                debug ("Storing model with %u rows", model.get_n_rows());
                resources.store ((Dee.SequenceModel)model, "com.canonical.Friends.Streams");
                return true;
            });
        }

        var settings = new Settings ("com.canonical.friends");
        settings.bind("interval", this, "interval", 0);

        Bus.get_proxy.begin<Dispatcher>(BusType.SESSION,
            "com.canonical.Friends.Dispatcher",
            "/com/canonical/friends/Dispatcher",
            DBusProxyFlags.NONE, null, on_proxy_cb);
    }

    private void on_proxy_cb (GLib.Object? obj, GLib.AsyncResult res)
    {
        try {
            dispatcher = Bus.get_proxy.end(res);
            Timeout.add_seconds (120, fetch_contacts);
            Timeout.add_seconds (300, expire_avatars);
            var ret = on_refresh ();
        } catch (IOError e) {
            warning (e.message);
        }
    }

    bool on_refresh ()
    {
        debug ("Interval is %d", interval);
        // By default, this happens immediately on startup, and then
        // every 15 minutes thereafter.
        Timeout.add_seconds ((interval * 60), on_refresh);
        try {
            dispatcher.Refresh ();
        } catch (IOError e) {
            warning ("Failed to refresh - %s", e.message);
        }
        return false;
    }

    bool fetch_contacts ()
    {
        debug ("Fetching contacts...");
        // By default, this happens 2 minutes after startup, and then
        // every 24 hours thereafter.
        Timeout.add_seconds (86400, fetch_contacts);
        try {
            dispatcher.Do ("contacts", "", "");
        } catch (IOError e) {
            warning ("Failed to fetch contacts - %s", e.message);
        }
        return false;
    }

    bool expire_avatars ()
    {
        debug ("Expiring old avatars...");
        // By default, this happens 5 minutes after startup, and then
        // every 7 days thereafter.
        Timeout.add_seconds (604800, expire_avatars);
        try {
            dispatcher.ExpireAvatars ();
        } catch (IOError e) {
            warning ("Failed to expire avatars - %s", e.message);
        }
        return false;
    }
}

void on_bus_aquired (DBusConnection conn) {
    try {
        conn.register_object ("/com/canonical/friends/Service", new Master ());
    } catch (IOError e) {
        stderr.printf ("Could not register service\n");
    }
}

public static int main (string[] args)
{
    Bus.own_name (BusType.SESSION, "com.canonical.Friends.Service", BusNameOwnerFlags.NONE,
                  on_bus_aquired,
                  () => {},
                  () => stderr.printf ("Could not aquire name\n"));
    new MainLoop().run();
    return 0;
}
