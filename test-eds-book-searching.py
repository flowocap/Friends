#!/usr/bin/python

from gi.repository import EBook, EDataServer, Gio, GLib


def search(ml):
	registry = EDataServer.SourceRegistry.new_sync(None)  
	source = None
	for previous_source in registry.list_sources(None):
		if previous_source.get_display_name() == "test-fb-contacts":
			source = registry.ref_source(previous_source.get_uid())

	if(source is None):
		print("No Source found !")
		return
	else:
		print("yep found the source")
		
	client = EBook.BookClient.new(source)
	client.open_sync(False, None)

	q = EBook.book_query_vcard_field_test("facebook-id", EBook.BookQueryTest(0), "9999999")
	cs = client.get_contacts_sync(q.to_string(), Gio.Cancellable())
		
	if cs[0] == False:
		print("Search ")
	else:
		print(str(cs))
		print("Found something %i", len(cs[1]))    
		for c in cs[1]:
			facebook_id_attr = c.get_attribute("facebook-id")
			facebook_name = c.get_attribute("facebook-name")
			print("Found contact with attr %s and %s", facebook_id_attr.get_value(), facebook_name.get_value())
	ml.quit()

ml = GLib.MainLoop()
GLib.idle_add(search, ml)
ml.run()

