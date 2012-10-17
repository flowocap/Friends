from gi.repository import EBook, EDataServer, Gio, GLib

def create(ml):
	registry = EDataServer.SourceRegistry.new_sync(None)
	for previous_source in registry.list_sources(None):
		if previous_source.get_display_name() == "test-fb-contacts":
			source = registry.ref_source(previous_source.get_uid())
	if(source is None):
		print("No source from reg %s", uid)
	else:
		print("creating contact and pushing to book")
		client = EBook.BookClient.new(source)
		client.open_sync(False, None)
		c =  EBook.Contact.new()
		vcafid = EBook.VCardAttribute.new("social-networking-attributes", "facebook-id")      
		vcafid.add_value("9999999")
		vcafn = EBook.VCardAttribute.new("social-networking-attributes", "facebook-name")      
		vcafn.add_value("Conor Curran")
		vcard = EBook.VCard.new()
		vcard.add_attribute(vcafid)
		vcard.add_attribute(vcafn)
		c = EBook.Contact.new_from_vcard(vcard.to_string(EBook.VCardFormat(1)))
		res = client.add_contact_sync(c, Gio.Cancellable());
		print("add contact result %s", res)
	ml.quit()

ml = GLib.MainLoop()
GLib.idle_add(create, ml)
ml.run()
