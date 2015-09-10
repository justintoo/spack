#------------------------------------------------------------------------------
# Author: Justin Too <too1@llnl.gov>
#------------------------------------------------------------------------------

from spack import *

import os
import sys

from glob import glob

class Rose(Package):
    """A compiler infrastructure to build source-to-source program
       transformation and analysis tools.
       (Developed at Lawrence Livermore National Lab)"""

    #-------------------------------------------------------------
    # Meta Info
    #-------------------------------------------------------------
    homepage = "http://rosecompiler.org/"
    url      = "https://github.com/rose-compiler/edg4x-rose"

    #-------------------------------------------------------------
    # Versions
    #-------------------------------------------------------------
    version('master', branch='master', git='https://github.com/rose-compiler/rose.git')
    version('dev', branch='master', git='https://github.com/rose-compiler/rose-develop.git')

    #-------------------------------------------------------------
    # Variants
    #-------------------------------------------------------------
    variant('debug', default=False, description="enable debug symbols")

    #-------------------------------------------------------------
    # Patches
    #-------------------------------------------------------------
    patch('add_spack_compiler_recognition.patch')

    #-------------------------------------------------------------
    # Dependencies
    #-------------------------------------------------------------
    depends_on("autoconf@2.69:")
    depends_on("automake@1.14:")
    depends_on("libtool@2.4:")

    depends_on("gcc@4.8.4 %gcc@4.4.7")
    #depends_on("gcc@4.4.7:4.8.4")
    #depends_on('gcc@4.7:', when='^boost@1.50:')

    depends_on("boost@1.54.0")
    depends_on('boost@1.54:', when='%gcc@4.7:')
    depends_on("boost@1.47:1.54.0")

    depends_on("jdk@8u25-linux-x64")

    # Graphviz < Ghostscript
    #
    # ncurses:
    #   Installing with GCC 4.4.7 because 4.8.4 fails compilation.
    #
    #   Disabling wide character configuration because for some
    #   reason it will only install libncursesw and not libncurses.
    #
    # readline:
    #    Installing with GCC 4.4.7 in order for Spack to correctly
    #    detect the ncurses, which was installed with GCC 4.4..
    #
    depends_on("ghostscript")
    depends_on("ncurses -widec %gcc@4.4.7", when='^ghostscript')
    depends_on("readline %gcc@4.4.7", when='^ncurses %gcc@4.4.7')
    # TODO: 9/9/15 GraphViz website is temporarily down... G_G
    #depends_on("graphviz")

    # swig:
    #    Installing with GCC 4.4.7 because 4.8.4 fails compilation:
    #
    #    /opt/spack/develop/spack-develop/opt/spack/unknown_arch/gcc-4.4.7/binutils-2.25-aptwtoplnpaspjyfby3vddjhxvhw45mp/bin/ld: pcrecpp_unittest-pcrecpp_unittest.o: undefined reference to symbol '_Unwind_Resume@@GCC_3.0'
    #    /opt/spack/develop/spack-develop/opt/spack/unknown_arch/gcc-4.4.7/gcc-4.8.4-7khq5zqbuf2akxbw6guv43gdt3cdztwz/lib64/libgcc_s.so.1: error adding symbols: DSO missing from command line
    depends_on("swig %gcc@4.4.7")

    #-------------------------------------------------------------
    # Install
    #-------------------------------------------------------------
    def install(self, spec, prefix):
        #---------------------------------------------------------
        # Bootstrap with autotools
        #---------------------------------------------------------
        bash = which('bash')
        if not os.path.isfile('configure'):
            bash('build')

        #---------------------------------------------------------
        # Dependencies
        #---------------------------------------------------------
        gcc   = spec['gcc']
        boost = spec['boost']
        jdk   = spec['jdk']

        #---------------------------------------------------------
        # Configuration Options
        #---------------------------------------------------------
        configure_args = [
            "--prefix=%s" % prefix,
            "--with-boost=%s" % boost.prefix,
            ]

        #---------------------------------------------------------
        # GCC
        #---------------------------------------------------------
        if '^gcc@4.9:' in spec:
            print >> sys.stderr, '[Warning] You are using an unsupported version of GCC'
            configure_args.append('--disable-gcc-version-check')

        # https://gcc.gnu.org/ml/gcc/2004-04/msg01032.html
        #if '^gcc@4.8:' in spec:
        configure_args.append('LDFLAGS=-L%s -lgcc_s' % gcc.prefix.lib)
        configure_args.append('CPPFLAGS=-L%s -lgcc_s' % gcc.prefix.lib)

        #---------------------------------------------------------
        # Boost
        #---------------------------------------------------------
        if '^boost@1.54:' in spec:
            print >> sys.stderr, '[Warning] You are using an unsupported version of Boost'
            configure_args.append('--disable-boost-version-check')

        #---------------------------------------------------------
        # Java
        #---------------------------------------------------------
        # JDK/lib
        self.rpath.append("FOOOOOOBARRRRRRR")
        self.rpath.append(jdk.prefix.lib)

        # E.g: JDK/jre/lib/amd64/server/ which contains libjvm.so
        os.path.join(jdk.prefix.lib)
        jdk_server_libdir = glob(join_path(jdk.prefix, "jre/lib/*/server"))
        if jdk_server_libdir:
            self.rpath.append(jdk_server_libdir[0])

        # TODO: Figure out how to correctly set RPATHs so we can remove this
        # LD_LIBRARY_PATH modification, otherwise user's will have to add to
        # their environment.
        os.environ['LD_LIBRARY_PATH'] = "%s:%s" % (jdk_server_libdir[0], jdk.prefix.lib)

        libjvm = join_path(jdk_server_libdir[0], 'libjvm.so')
        libjvm_rose_lib = join_path(self.prefix.lib, 'libjvm.so')
        if os.path.islink(libjvm_rose_lib):
            os.unlink(libjvm_rose_lib)

        symlink(libjvm, libjvm_rose_lib)

        #---------------------------------------------------------
        # Debug
        #---------------------------------------------------------
        # TODO:
        if '+debug' in spec:
            configure_args.append('')

        #---------------------------------------------------------
        # Configure, compile & install
        #---------------------------------------------------------
        with working_dir('rose-build', create=True):
            configure = Executable('../configure')
            configure(*configure_args)

            make('install-core', 'V=1')

