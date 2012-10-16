#!/usr/bin/python

from gi.repository import EBook, EDataServer, Gio, GLib

registry = EDataServer.SourceRegistry.new_sync(None)  
source = None

ml = GLib.MainLoop()
GLib.timeout_add_seconds(2, ml.quit)
ml.run()

for previous_source in registry.list_sources(None):
	if previous_source.get_display_name() == "test-fb-contacts":
		source = registry.ref_source(previous_source.get_uid())

if(source is None):
	print("Hello and Bollox")
else:
	print("yep founded")
	
client = EBook.BookClient.new(source)
client.open_sync(False, None)
GLib.timeout_add_seconds(2, ml.quit)
ml.run()

q = EBook.book_query_vcard_field_test("facebook-id", EBook.BookQueryTest(0), "999999")
cs = client.get_contacts_sync(q.to_string(), Gio.Cancellable())
x = client.get_contact_sync("pas-id-507D991B00000001", Gio.Cancellable())
if(x is None):
	print("couldn't find the contact with the given uid")
else:
	facebook_name = x.get_attribute("facebook-name")
	print("found contact %s", facebook_name)
	
GLib.timeout_add_seconds(2, ml.quit)
ml.run()


if cs[0] == False:
	print("Found nada")
else:
	print(str(cs))
	print("Found something %i", len(cs[1]))    
	for c in cs[1]:
		facebook_id_attr = c.get_attribute("facebook-id")
		facebook_name = c.get_attribute("facebook-name")
		print("Found contact with attr %s and %s", facebook_id_attr, facebook_name)
