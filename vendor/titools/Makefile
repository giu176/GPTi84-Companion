prefix = /usr/local
exec_prefix = ${prefix}
datarootdir = ${prefix}/share
bindir = ${exec_prefix}/bin
mandir = ${datarootdir}/man

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

top_srcdir = .
top_builddir = .

distname = titools-0.1

distfiles = README COPYING \
	    configure config.h.in configure.ac install-sh \
	    Makefile.in src/Makefile.in doc/Makefile.in \
	    src/*.c src/*.h doc/*.1 compat/*.h

all:
	cd src && $(MAKE) all

clean:
	cd src && $(MAKE) clean

distclean: clean
	rm -f config.h config.log config.status
	rm -rf aclocal.m4 autom4te.cache
	rm -f src/Makefile doc/Makefile Makefile

install:
	cd src && $(MAKE) install
	cd doc && $(MAKE) install

uninstall:
	cd src && $(MAKE) uninstall
	cd doc && $(MAKE) uninstall

dist:
	rm -rf $(distname)
	mkdir $(distname)
	mkdir $(distname)/src
	mkdir $(distname)/doc
	mkdir $(distname)/compat
	set -e ; for i in $(distfiles) ; do \
	 cp -p $$i $(distname)/$$i ; \
	done
	tar cfvz $(distname).tgz $(distname)

.PHONY: all clean distclean install uninstall dist
