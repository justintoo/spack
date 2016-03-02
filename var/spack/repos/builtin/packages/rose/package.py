#------------------------------------------------------------------------------
# Author: Justin Too <too1@llnl.gov>
#------------------------------------------------------------------------------

from spack import *

class Rose(Package):
    """A compiler infrastructure to build source-to-source program
       transformation and analysis tools.
       (Developed at Lawrence Livermore National Lab)"""

    homepage = "http://rosecompiler.org/"
    url      = "https://github.com/rose-compiler/rose-develop"

    version('master', commit='65884c443a04d04d5ec81cd01adedff0bcb530a4', git='https://github.com/rose-compiler/rose-develop.git')

    depends_on("autoconf@2.69")
    depends_on("automake@1.14")
    depends_on("libtool@2.4")
    depends_on("boost@1.57.0 %gcc@4.8.1")

    def validate_toolchain(self, spec):
        if not spec.satisfies("%gcc@4.8.1"):
            raise Exception("You are trying to use an unsupported compiler version to compile ROSE. The ROSE package currently only supports package compilation with GCC 4.8.1" % (gcc, gcc_version))

    def install(self, spec, prefix):
        self.validate_toolchain(spec)

        # Bootstrap with autotools
        bash = which('bash')
        bash('build')

        # Configure, compile & install
        with working_dir('rose-build', create=True):
            boost = spec['boost']

            configure = Executable('../configure')
            configure("--prefix=" + prefix,
                      "--enable-edg_version=4.9",
                      "--without-java",
                      "--with-boost=" + boost.prefix,
                      "--disable-boost-version-check",
                      "--enable-languages=c,c++,fortran,binaries")
            make("install-core")
            make("check")

