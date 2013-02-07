AC_INIT([friends-service], 0.1)
AM_INIT_AUTOMAKE([no-dist-gzip dist-bzip2])
AC_CONFIG_HEADERS([config.h])

AM_SILENT_RULES([yes])

AM_MAINTAINER_MODE

AM_PROG_VALAC([0.16])
AC_PROG_CC
AM_PROG_CC_STDC
AC_PROG_INSTALL

###########################
# GSETTINGS
###########################
GLIB_GSETTINGS

DEE_REQUIRED=1.0.0
PKG_CHECK_MODULES(BASE,
                  gio-2.0
                  dee-1.0 >= $DEE_REQUIRED)

AC_SUBST(BASE_CFLAGS)
AC_SUBST(BASE_LIBS)

AC_CONFIG_FILES([
        Makefile
        src/Makefile
        data/Makefile
])
AC_OUTPUT
