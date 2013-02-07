dbus_servicesdir = $(datadir)/dbus-1/services

service_in_files =  com.canonical.Friends.Service.service.in
dbus_services_DATA = $(service_in_files:.service.in=.service)

%.service: %.service.in
	sed -e "s|\@bindir\@|$(bindir)|" $< > $@

EXTRA_DIST = \
  $(service_in_files)

CLEANFILES = \
  $(dbus_services_DATA) 
