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


[DBus (name = "com.canonical.Friends.Dispatcher")]
private interface Dispatcher : GLib.Object {
        public abstract void Refresh () throws GLib.IOError;
}

[DBus (name = "com.canonical.Friends.Service")]
public class Master
{
    private Dee.Model model;
    private Dee.SharedModel shared_model;
    private unowned Dee.ResourceManager resources;
    private int interval;
    private Dispatcher dispatcher;

    public Master ()
    {
        resources = Dee.ResourceManager.get_default ();
        model = new Dee.SequenceModel ();
        Dee.SequenceModel? _m = null;

        try {
            _m = resources.load ("com.canonical.Friends.Streams") as Dee.SequenceModel;
        } catch (Error e) {
            debug ("Failed to load model from resource manager: %s", e.message);
        }

        if (_m is Dee.Model)
        {
            debug ("Got a valid model");
            model = _m;
        } else {
            debug ("Setting schema for a new model");
            model.set_schema (
                              "aas",
                              "s",
                              "s",
                              "s",
                              "s",
                              "b",
                              "s",
                              "s",
                              "s",
                              "s",
                              "d",
                              "b",
                              "s",
                              "s",
                              "s",
                              "s",
                              "s",
                              "s");
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

            Timeout.add_seconds (30, () => {
                shared_model.flush_revision_queue();
                debug ("Storing model with %u rows", model.get_n_rows());
                resources.store ((Dee.SequenceModel)model, "com.canonical.Friends.Streams");
                return true;
            });
        }

        var settings = new Settings ("com.canonical.friends");
        interval = settings.get_int ("interval").clamp (5,30);

        settings.changed["interval"].connect (() => {
            interval = settings.get_int ("interval").clamp (5,30);
            debug ("Interval changed: %d\n", interval);
        });

        Bus.get_proxy.begin<Dispatcher>(BusType.SESSION,
            "com.canonical.Friends.Dispatcher",
            "/com/canonical/friends/Dispatcher",
            DBusProxyFlags.NONE, null, on_proxy_cb);
    }

    private void on_proxy_cb (GLib.Object? obj, GLib.AsyncResult res)
    {
        try {
            dispatcher = Bus.get_proxy.end(res);
            var ret = on_refresh ();
        } catch (IOError e) {
            warning (e.message);
        }
    }

    bool on_refresh ()
    {
        debug ("Interval is %d", interval);
        Timeout.add_seconds ((interval * 60), on_refresh);
        try {
            dispatcher.Refresh ();
        } catch (IOError e) {
            warning ("Failed to refresh - %s", e.message);
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
