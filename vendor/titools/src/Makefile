prefix = /usr/local
exec_prefix = ${prefix}
bindir = ${exec_prefix}/bin

CC = gcc
CFLAGS = -g -O2 -W -Wall -Wwrite-strings
CPPFLAGS = 
DEFS = -DHAVE_CONFIG_H
INSTALL = /usr/bin/install -c
LDFLAGS = -L/home/xander/Documents/Dev/ti84-superdeluxe/build/tilibs-install/lib -Wl,-rpath,/home/xander/Documents/Dev/ti84-superdeluxe/build/tilibs-install/lib
LIBS = 

TICALCS_CFLAGS = -I/home/xander/Documents/Dev/ti84-superdeluxe/build/tilibs-install/include/tilp2 -I/usr/include/libusb-1.0 -I/usr/include/glib-2.0 -I/usr/lib/glib-2.0/include -I/usr/include/sysprof-6 -pthread
TICALCS_LIBS = -L/home/xander/Documents/Dev/ti84-superdeluxe/build/tilibs-install/lib -lticalcs2 -lglib-2.0


srcdir = .

top_srcdir = ..
top_builddir = ..

compile = $(CC) -I$(top_builddir) -I$(srcdir) $(CFLAGS) $(CPPFLAGS) $(TICALCS_CFLAGS) $(DEFS)
link = $(CC) $(CFLAGS) $(LDFLAGS)
libs = $(TICALCS_LIBS) $(LIBS)

programs = tiget \
	   tiinfo \
	   tikey \
	   tils \
	   tiput \
	   tirm \
	   tiscr

all: $(programs)

install: all
	$(INSTALL) -d -m 755 $(DESTDIR)$(bindir)
	set -e ; for i in $(programs) ; do \
	 $(INSTALL) -m 755 $$i $(DESTDIR)$(bindir) ; \
	done

uninstall:
	set -e ; for i in $(programs) ; do \
	 rm -f $(DESTDIR)$(bindir)/$$i ; \
	done

common.o: common.c titools.h
	$(compile) -c $(srcdir)/common.c

glob.o: glob.c titools.h
	$(compile) -c $(srcdir)/glob.c

tiget: tiget.o common.o glob.o
	$(link) -o tiget tiget.o common.o glob.o $(libs)
tiget.o: tiget.c titools.h
	$(compile) -c $(srcdir)/tiget.c

tiinfo: tiinfo.o common.o
	$(link) -o tiinfo tiinfo.o common.o $(libs)
tiinfo.o: tiinfo.c titools.h
	$(compile) -c $(srcdir)/tiinfo.c

tikey: tikey.o common.o
	$(link) -o tikey tikey.o common.o $(libs)
tikey.o: tikey.c titools.h
	$(compile) -c $(srcdir)/tikey.c

tils: tils.o common.o glob.o
	$(link) -o tils tils.o common.o glob.o $(libs)
tils.o: tils.c titools.h
	$(compile) -c $(srcdir)/tils.c

tiput: tiput.o common.o
	$(link) -o tiput tiput.o common.o $(libs)
tiput.o: tiput.c titools.h
	$(compile) -c $(srcdir)/tiput.c

tirm: tirm.o common.o glob.o
	$(link) -o tirm tirm.o common.o glob.o $(libs)
tirm.o: tirm.c titools.h
	$(compile) -c $(srcdir)/tirm.c

tiscr: tiscr.o common.o
	$(link) -o tiscr tiscr.o common.o $(libs)
tiscr.o: tiscr.c titools.h
	$(compile) -c $(srcdir)/tiscr.c

clean:
	rm -f $(programs)
	rm -f *.o

.PHONY: all clean install
