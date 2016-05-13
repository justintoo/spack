#------------------------------------------------------------------------------
# Author: Justin Too <too1@llnl.gov>
#------------------------------------------------------------------------------

import os
from spack import *

class Rose(Package):
    """A compiler infrastructure to build source-to-source program
       transformation and analysis tools.
       (Developed at Lawrence Livermore National Lab)"""

    homepage = "http://rosecompiler.org/"
    url      = "https://github.com/rose-compiler/rose-develop"

    version('0.9.7.16', commit='b2cc9cf0996c6b2598919e5cdcd88c1cd1806030', git='https://github.com/rose-compiler/rose-develop.git')

    depends_on("autoconf@2.69")
    depends_on("automake@1.14")
    depends_on("libtool@2.4")
    depends_on("boost@1.55.0 %gcc@4.8.3")

    def validate_toolchain(self, spec):
        if not spec.satisfies("%gcc@4.8.3"):
            raise Exception("You are trying to use an unsupported compiler version to compile ROSE. The ROSE package currently only supports package compilation with GCC 4.8.3" % (gcc, gcc_version))

    def install(self, spec, prefix):
        self.validate_toolchain(spec)

        # Bootstrap with autotools
        bash = which('bash')
        bash('build')

        mpicc = which('mpicc')
        mpicxx = which('mpic++')

        # Configure, compile & install
        with working_dir('rose-build', create=True):
            boost = spec['boost']

            configure = Executable(os.path.abspath('../configure'))
            configure("--prefix=" + prefix,
                      "--enable-edg_version=4.9",
                      "--without-java",
                      "--with-boost=" + boost.prefix,
                      "--with-alternate_backend_C_compiler=" + str(mpicc),
                      "--with-alternate_backend_Cxx_compiler=" + str(mpicxx),
                      "--disable-boost-version-check",
                      "--enable-languages=c,c++,fortran,binaries")
            make("install-core")
            #make("check")

