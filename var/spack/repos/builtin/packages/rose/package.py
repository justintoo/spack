##############################################################################
# Copyright (c) 2013-2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
#
# This file is part of Spack.
# Created by Todd Gamblin, tgamblin@llnl.gov, All rights reserved.
# LLNL-CODE-647188
#
# For details, see https://github.com/llnl/spack
# Please also see the LICENSE file for our notice and the LGPL.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License (as
# published by the Free Software Foundation) version 2.1, February 1999.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the IMPLIED WARRANTY OF
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the terms and
# conditions of the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
##############################################################################
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

    version('0.9.7.21', commit='8924055d0f1e01ba37053fe5068a7989ff2c7874', git='https://github.com/rose-compiler/rose-develop.git')
    version('0.9.7.16', commit='b2cc9cf0996c6b2598919e5cdcd88c1cd1806030', git='https://github.com/rose-compiler/rose-develop.git')
    # Placeholder for automated testing
    # version('__ROSE_VERSION__', commit='__ROSE_COMMIT__', git='rose-dev@rosecompiler1.llnl.gov:rose/scratch/rose.git')
    # ADD_EXTRA_VERSIONS_HERE

    depends_on("autoconf@2.69")
    depends_on("automake@1.14")
    depends_on("libtool@2.4")
    depends_on("__BOOST_VERSION__")

    def validate_toolchain(self, spec):
        if not (spec.satisfies("%gcc@4.8.5") or spec.satisfies("%intel@16.0.3")):
            raise Exception("You are trying to use an unsupported compiler version to compile ROSE. The ROSE package currently only supports package compilation with GCC 4.8.5 or Intel 16.0.3")

    def install(self, spec, prefix):
        self.validate_toolchain(spec)

        # Checkout EDG submodule
        git = which('git')
        git('submodule', 'update', '--init')

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
                      "--enable-edg_version=4.12",
                      "--without-java",
                      "--with-boost=" + boost.prefix,
                      "--with-alternate_backend_C_compiler=" + str(mpicc),
                      "--with-alternate_backend_Cxx_compiler=" + str(mpicxx),
                      "--disable-boost-version-check",
                      "--enable-languages=c,c++,fortran,binaries")
            #make("install-core")
            srun = which('srun')
            srun('-ppdebug', 'make', '-j16', 'install-core')
            make("install", "-C", "bin/")
            #make("check")

