from gi.repository import EBook, EDataServer, Gio, GLib
import time

uid = None

reg = EDataServer.SourceRegistry.new_sync(None)  
source = EDataServer.Source.new(None, None)
source.set_display_name("test-fb-contacts")
source.set_parent("local-stub")        
extension = source.get_extension(EDataServer.SOURCE_EXTENSION_ADDRESS_BOOK)
extension.set_backend_name("local")

if(reg.commit_source_sync(source, Gio.Cancellable())):
	print("source creation successfull")
	uid = source.get_uid()
time.sleep(1)

if(uid == None):
	print("Bollox")

ml = GLib.MainLoop()
GLib.timeout_add_seconds(2, ml.quit)
ml.run()

source_match = reg.ref_source(uid)

if(source_match is None):
	print("No source match from reg %s", uid)
else:
	print("creating contact and pushing to book")
	client = EBook.BookClient.new(source_match)
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
