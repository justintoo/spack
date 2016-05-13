from spack import *


class Visit(Package):
    """VisIt is an Open Source, interactive, scalable, visualization, animation and analysis tool."""
    homepage = "https://wci.llnl.gov/simulation/computer-codes/visit/"
    url = "http://portal.nersc.gov/project/visit/releases/2.10.1/visit2.10.1.tar.gz"

    version('2.10.1', '3cbca162fdb0249f17c4456605c4211e')
    version('2.10.2', '253de0837a9d69fb689befc98ea4d068')

    depends_on("vtk@6.1.0~opengl2")
    depends_on("qt@4.8.6")
    depends_on("python")
    depends_on("silo+shared")

    def install(self, spec, prefix):
        with working_dir('spack-build', create=True):

            feature_args = std_cmake_args[:]
            feature_args.extend(["-DVTK_MAJOR_VERSION=6",
                                 "-DVTK_MINOR_VERSION=1",
                                 "-DVISIT_LOC_QMAKE_EXE:FILEPATH=%s/qmake-qt4" % spec['qt'].prefix.bin,
                                 "-DPYTHON_EXECUTABLE:FILEPATH=%s/python" % spec['python'].prefix.bin,
                                 "-DVISIT_SILO_DIR:PATH=%s" % spec['silo'].prefix,
                                 "-DVISIT_HDF5_DIR:PATH=%s" % spec['hdf5'].prefix])

            cmake('../src', *feature_args)

            make()
            make("install")
