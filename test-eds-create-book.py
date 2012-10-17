from gi.repository import EBook, EDataServer, Gio, GLib

def delete_previous(registry):
	for previous_source in registry.list_sources(None):
		if previous_source.get_display_name() == "test-fb-contacts":
			source = registry.ref_source(previous_source.get_uid())
			res = source.remove_sync(Gio.Cancellable())
			print("Deleted previous found source - deletion result = %s", str(res))


def create(ml):
	uid = None
	reg = EDataServer.SourceRegistry.new_sync(None)  
	delete_previous(reg)
	source = EDataServer.Source.new(None, None)
	source.set_display_name("test-fb-contacts")
	source.set_parent("local-stub")       
	extension = source.get_extension(EDataServer.SOURCE_EXTENSION_ADDRESS_BOOK)
	extension.set_backend_name("local")
	if(reg.commit_source_sync(source, Gio.Cancellable())):
		print("source creation successfull")
	ml.quit()

ml = GLib.MainLoop()
GLib.idle_add(create, ml)
ml.run()
