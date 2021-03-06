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
import collections
import errno
import fileinput
import fnmatch
import glob
import numbers
import os
import re
import shutil
import six
import stat
import subprocess
import sys
from contextlib import contextmanager

from llnl.util import tty
from llnl.util.lang import dedupe

__all__ = [
    'FileFilter',
    'HeaderList',
    'LibraryList',
    'ancestor',
    'can_access',
    'change_sed_delimiter',
    'copy_mode',
    'filter_file',
    'find',
    'find_headers',
    'find_libraries',
    'find_system_libraries',
    'fix_darwin_install_name',
    'force_remove',
    'force_symlink',
    'hide_files',
    'install',
    'install_tree',
    'is_exe',
    'join_path',
    'mkdirp',
    'remove_dead_links',
    'remove_if_dead_link',
    'remove_linked_tree',
    'set_executable',
    'set_install_permissions',
    'touch',
    'touchp',
    'traverse_tree',
    'unset_executable_mode',
    'working_dir'
]


def filter_file(regex, repl, *filenames, **kwargs):
    r"""Like sed, but uses python regular expressions.

    Filters every line of each file through regex and replaces the file
    with a filtered version.  Preserves mode of filtered files.

    As with re.sub, ``repl`` can be either a string or a callable.
    If it is a callable, it is passed the match object and should
    return a suitable replacement string.  If it is a string, it
    can contain ``\1``, ``\2``, etc. to represent back-substitution
    as sed would allow.

    Parameters:
        regex (str): The regular expression to search for
        repl (str): The string to replace matches with
        *filenames: One or more files to search and replace

    Keyword Arguments:
        string (bool): Treat regex as a plain string. Default it False
        backup (bool): Make backup file(s) suffixed with ``~``. Default is True
        ignore_absent (bool): Ignore any files that don't exist.
            Default is False
    """
    string = kwargs.get('string', False)
    backup = kwargs.get('backup', True)
    ignore_absent = kwargs.get('ignore_absent', False)

    # Allow strings to use \1, \2, etc. for replacement, like sed
    if not callable(repl):
        unescaped = repl.replace(r'\\', '\\')

        def replace_groups_with_groupid(m):
            def groupid_to_group(x):
                return m.group(int(x.group(1)))
            return re.sub(r'\\([1-9])', groupid_to_group, unescaped)
        repl = replace_groups_with_groupid

    if string:
        regex = re.escape(regex)

    for filename in filenames:
        backup_filename = filename + "~"

        if ignore_absent and not os.path.exists(filename):
            continue

        # Create backup file. Don't overwrite an existing backup
        # file in case this file is being filtered multiple times.
        if not os.path.exists(backup_filename):
            shutil.copy(filename, backup_filename)

        try:
            for line in fileinput.input(filename, inplace=True):
                print(re.sub(regex, repl, line.rstrip('\n')))
        except:
            # clean up the original file on failure.
            shutil.move(backup_filename, filename)
            raise

        finally:
            if not backup:
                os.remove(backup_filename)


class FileFilter(object):
    """Convenience class for calling ``filter_file`` a lot."""

    def __init__(self, *filenames):
        self.filenames = filenames

    def filter(self, regex, repl, **kwargs):
        return filter_file(regex, repl, *self.filenames, **kwargs)


def change_sed_delimiter(old_delim, new_delim, *filenames):
    """Find all sed search/replace commands and change the delimiter.

    e.g., if the file contains seds that look like ``'s///'``, you can
    call ``change_sed_delimiter('/', '@', file)`` to change the
    delimiter to ``'@'``.

    Note that this routine will fail if the delimiter is ``'`` or ``"``.
    Handling those is left for future work.

    Parameters:
        old_delim (str): The delimiter to search for
        new_delim (str): The delimiter to replace with
        *filenames: One or more files to search and replace
    """
    assert(len(old_delim) == 1)
    assert(len(new_delim) == 1)

    # TODO: handle these cases one day?
    assert(old_delim != '"')
    assert(old_delim != "'")
    assert(new_delim != '"')
    assert(new_delim != "'")

    whole_lines = "^s@([^@]*)@(.*)@[gIp]$"
    whole_lines = whole_lines.replace('@', old_delim)

    single_quoted = r"'s@((?:\\'|[^@'])*)@((?:\\'|[^'])*)@[gIp]?'"
    single_quoted = single_quoted.replace('@', old_delim)

    double_quoted = r'"s@((?:\\"|[^@"])*)@((?:\\"|[^"])*)@[gIp]?"'
    double_quoted = double_quoted.replace('@', old_delim)

    repl = r's@\1@\2@g'
    repl = repl.replace('@', new_delim)

    for f in filenames:
        filter_file(whole_lines, repl, f)
        filter_file(single_quoted, "'%s'" % repl, f)
        filter_file(double_quoted, '"%s"' % repl, f)


def set_install_permissions(path):
    """Set appropriate permissions on the installed file."""
    if os.path.isdir(path):
        os.chmod(path, 0o755)
    else:
        os.chmod(path, 0o644)


def copy_mode(src, dest):
    src_mode = os.stat(src).st_mode
    dest_mode = os.stat(dest).st_mode
    if src_mode & stat.S_IXUSR:
        dest_mode |= stat.S_IXUSR
    if src_mode & stat.S_IXGRP:
        dest_mode |= stat.S_IXGRP
    if src_mode & stat.S_IXOTH:
        dest_mode |= stat.S_IXOTH
    os.chmod(dest, dest_mode)


def unset_executable_mode(path):
    mode = os.stat(path).st_mode
    mode &= ~stat.S_IXUSR
    mode &= ~stat.S_IXGRP
    mode &= ~stat.S_IXOTH
    os.chmod(path, mode)


def install(src, dest):
    """Manually install a file to a particular location."""
    tty.debug("Installing %s to %s" % (src, dest))

    # Expand dest to its eventual full path if it is a directory.
    if os.path.isdir(dest):
        dest = join_path(dest, os.path.basename(src))

    shutil.copy(src, dest)
    set_install_permissions(dest)
    copy_mode(src, dest)


def install_tree(src, dest, **kwargs):
    """Manually install a directory tree to a particular location."""
    tty.debug("Installing %s to %s" % (src, dest))
    shutil.copytree(src, dest, **kwargs)

    for s, d in traverse_tree(src, dest, follow_nonexisting=False):
        set_install_permissions(d)
        copy_mode(s, d)


def is_exe(path):
    """True if path is an executable file."""
    return os.path.isfile(path) and os.access(path, os.X_OK)


def mkdirp(*paths):
    """Creates a directory, as well as parent directories if needed."""
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)
        elif not os.path.isdir(path):
            raise OSError(errno.EEXIST, "File already exists", path)


def force_remove(*paths):
    """Remove files without printing errors.  Like ``rm -f``, does NOT
       remove directories."""
    for path in paths:
        try:
            os.remove(path)
        except OSError:
            pass


@contextmanager
def working_dir(dirname, **kwargs):
    if kwargs.get('create', False):
        mkdirp(dirname)

    orig_dir = os.getcwd()
    os.chdir(dirname)
    yield
    os.chdir(orig_dir)


@contextmanager
def hide_files(*file_list):
    try:
        baks = ['%s.bak' % f for f in file_list]
        for f, bak in zip(file_list, baks):
            shutil.move(f, bak)
        yield
    finally:
        for f, bak in zip(file_list, baks):
            shutil.move(bak, f)


def touch(path):
    """Creates an empty file at the specified path."""
    with open(path, 'a'):
        os.utime(path, None)


def touchp(path):
    """Like ``touch``, but creates any parent directories needed for the file.
    """
    mkdirp(os.path.dirname(path))
    touch(path)


def force_symlink(src, dest):
    try:
        os.symlink(src, dest)
    except OSError:
        os.remove(dest)
        os.symlink(src, dest)


def join_path(prefix, *args):
    path = str(prefix)
    for elt in args:
        path = os.path.join(path, str(elt))
    return path


def ancestor(dir, n=1):
    """Get the nth ancestor of a directory."""
    parent = os.path.abspath(dir)
    for i in range(n):
        parent = os.path.dirname(parent)
    return parent


def can_access(file_name):
    """True if we have read/write access to the file."""
    return os.access(file_name, os.R_OK | os.W_OK)


def traverse_tree(source_root, dest_root, rel_path='', **kwargs):
    """Traverse two filesystem trees simultaneously.

    Walks the LinkTree directory in pre or post order.  Yields each
    file in the source directory with a matching path from the dest
    directory, along with whether the file is a directory.
    e.g., for this tree::

        root/
          a/
            file1
            file2
          b/
            file3

    When called on dest, this yields::

        ('root',         'dest')
        ('root/a',       'dest/a')
        ('root/a/file1', 'dest/a/file1')
        ('root/a/file2', 'dest/a/file2')
        ('root/b',       'dest/b')
        ('root/b/file3', 'dest/b/file3')

    Keyword Arguments:
        order (str): Whether to do pre- or post-order traversal. Accepted
            values are 'pre' and 'post'
        ignore (str): Predicate indicating which files to ignore
        follow_nonexisting (bool): Whether to descend into directories in
            ``src`` that do not exit in ``dest``. Default is True
        follow_links (bool): Whether to descend into symlinks in ``src``
    """
    follow_nonexisting = kwargs.get('follow_nonexisting', True)
    follow_links = kwargs.get('follow_link', False)

    # Yield in pre or post order?
    order = kwargs.get('order', 'pre')
    if order not in ('pre', 'post'):
        raise ValueError("Order must be 'pre' or 'post'.")

    # List of relative paths to ignore under the src root.
    ignore = kwargs.get('ignore', lambda filename: False)

    # Don't descend into ignored directories
    if ignore(rel_path):
        return

    source_path = os.path.join(source_root, rel_path)
    dest_path = os.path.join(dest_root, rel_path)

    # preorder yields directories before children
    if order == 'pre':
        yield (source_path, dest_path)

    for f in os.listdir(source_path):
        source_child = os.path.join(source_path, f)
        dest_child = os.path.join(dest_path, f)
        rel_child = os.path.join(rel_path, f)

        # Treat as a directory
        if os.path.isdir(source_child) and (
                follow_links or not os.path.islink(source_child)):

            # When follow_nonexisting isn't set, don't descend into dirs
            # in source that do not exist in dest
            if follow_nonexisting or os.path.exists(dest_child):
                tuples = traverse_tree(
                    source_root, dest_root, rel_child, **kwargs)
                for t in tuples:
                    yield t

        # Treat as a file.
        elif not ignore(os.path.join(rel_path, f)):
            yield (source_child, dest_child)

    if order == 'post':
        yield (source_path, dest_path)


def set_executable(path):
    mode = os.stat(path).st_mode
    if mode & stat.S_IRUSR:
        mode |= stat.S_IXUSR
    if mode & stat.S_IRGRP:
        mode |= stat.S_IXGRP
    if mode & stat.S_IROTH:
        mode |= stat.S_IXOTH
    os.chmod(path, mode)


def remove_dead_links(root):
    """Removes any dead link that is present in root.

    Parameters:
        root (str): path where to search for dead links
    """
    for file in os.listdir(root):
        path = join_path(root, file)
        remove_if_dead_link(path)


def remove_if_dead_link(path):
    """Removes the argument if it is a dead link.

    Parameters:
        path (str): The potential dead link
    """
    if os.path.islink(path):
        real_path = os.path.realpath(path)
        if not os.path.exists(real_path):
            os.unlink(path)


def remove_linked_tree(path):
    """Removes a directory and its contents.

    If the directory is a symlink, follows the link and removes the real
    directory before removing the link.

    Parameters:
        path (str): Directory to be removed
    """
    if os.path.exists(path):
        if os.path.islink(path):
            shutil.rmtree(os.path.realpath(path), True)
            os.unlink(path)
        else:
            shutil.rmtree(path, True)


def fix_darwin_install_name(path):
    """Fix install name of dynamic libraries on Darwin to have full path.

    There are two parts of this task:

    1. Use ``install_name('-id', ...)`` to change install name of a single lib
    2. Use ``install_name('-change', ...)`` to change the cross linking between
       libs. The function assumes that all libraries are in one folder and
       currently won't follow subfolders.

    Parameters:
        path (str): directory in which .dylib files are located
    """
    libs = glob.glob(join_path(path, "*.dylib"))
    for lib in libs:
        # fix install name first:
        subprocess.Popen(
            ["install_name_tool", "-id", lib, lib],
            stdout=subprocess.PIPE).communicate()[0]
        long_deps = subprocess.Popen(
            ["otool", "-L", lib],
            stdout=subprocess.PIPE).communicate()[0].split('\n')
        deps = [dep.partition(' ')[0][1::] for dep in long_deps[2:-1]]
        # fix all dependencies:
        for dep in deps:
            for loc in libs:
                # We really want to check for either
                #     dep == os.path.basename(loc)   or
                #     dep == join_path(builddir, os.path.basename(loc)),
                # but we don't know builddir (nor how symbolic links look
                # in builddir). We thus only compare the basenames.
                if os.path.basename(dep) == os.path.basename(loc):
                    subprocess.Popen(
                        ["install_name_tool", "-change", dep, loc, lib],
                        stdout=subprocess.PIPE).communicate()[0]
                    break


def find(root, files, recurse=True):
    """Search for ``files`` starting from the ``root`` directory.

    Like GNU/BSD find but written entirely in Python.

    Examples:

    .. code-block:: console

       $ find /usr -name python

    is equivalent to:

    >>> find('/usr', 'python')

    .. code-block:: console

       $ find /usr/local/bin -maxdepth 1 -name python

    is equivalent to:

    >>> find('/usr/local/bin', 'python', recurse=False)

    Accepts any glob characters accepted by fnmatch:

    =======  ====================================
    Pattern  Meaning
    =======  ====================================
    *        matches everything
    ?        matches any single character
    [seq]    matches any character in ``seq``
    [!seq]   matches any character not in ``seq``
    =======  ====================================

    Parameters:
        root (str): The root directory to start searching from
        files (str or collections.Sequence): Library name(s) to search for
        recurse (bool, optional): if False search only root folder,
            if True descends top-down from the root. Defaults to True.

    Returns:
        :func:`list`: The files that have been found
    """
    if isinstance(files, six.string_types):
        files = [files]

    if recurse:
        return _find_recursive(root, files)
    else:
        return _find_non_recursive(root, files)


def _find_recursive(root, search_files):
    found_files = []

    for path, _, list_files in os.walk(root):
        for search_file in search_files:
            for list_file in list_files:
                if fnmatch.fnmatch(list_file, search_file):
                    found_files.append(join_path(path, list_file))

    return found_files


def _find_non_recursive(root, search_files):
    found_files = []

    for list_file in os.listdir(root):
        for search_file in search_files:
            if fnmatch.fnmatch(list_file, search_file):
                found_files.append(join_path(root, list_file))

    return found_files


# Utilities for libraries and headers


class FileList(collections.Sequence):
    """Sequence of absolute paths to files.

    Provides a few convenience methods to manipulate file paths.
    """

    def __init__(self, files):
        if isinstance(files, six.string_types):
            files = [files]

        self.files = list(dedupe(files))

    @property
    def directories(self):
        """Stable de-duplication of the directories where the files reside.

        >>> l = LibraryList(['/dir1/liba.a', '/dir2/libb.a', '/dir1/libc.a'])
        >>> assert l.directories == ['/dir1', '/dir2']
        >>> h = HeaderList(['/dir1/a.h', '/dir1/b.h', '/dir2/c.h'])
        >>> assert h.directories == ['/dir1', '/dir2']
        """
        return list(dedupe(
            os.path.dirname(x) for x in self.files if os.path.dirname(x)
        ))

    @property
    def basenames(self):
        """Stable de-duplication of the base-names in the list

        >>> l = LibraryList(['/dir1/liba.a', '/dir2/libb.a', '/dir3/liba.a'])
        >>> assert l.basenames == ['liba.a', 'libb.a']
        >>> h = HeaderList(['/dir1/a.h', '/dir2/b.h', '/dir3/a.h'])
        >>> assert h.basenames == ['a.h', 'b.h']
        """
        return list(dedupe(os.path.basename(x) for x in self.files))

    @property
    def names(self):
        """Stable de-duplication of file names in the list

        >>> h = HeaderList(['/dir1/a.h', '/dir2/b.h', '/dir3/a.h'])
        >>> assert h.names == ['a', 'b']
        """
        return list(dedupe(x.split('.')[0] for x in self.basenames))

    def __getitem__(self, item):
        cls = type(self)
        if isinstance(item, numbers.Integral):
            return self.files[item]
        return cls(self.files[item])

    def __add__(self, other):
        return self.__class__(dedupe(self.files + list(other)))

    def __radd__(self, other):
        return self.__add__(other)

    def __eq__(self, other):
        return self.files == other.files

    def __len__(self):
        return len(self.files)

    def joined(self, separator=' '):
        return separator.join(self.files)

    def __repr__(self):
        return self.__class__.__name__ + '(' + repr(self.files) + ')'

    def __str__(self):
        return self.joined()


class HeaderList(FileList):
    """Sequence of absolute paths to headers.

    Provides a few convenience methods to manipulate header paths and get
    commonly used compiler flags or names.
    """

    def __init__(self, files):
        super(HeaderList, self).__init__(files)

        self._macro_definitions = []

    @property
    def headers(self):
        return self.files

    @property
    def include_flags(self):
        """Include flags

        >>> h = HeaderList(['/dir1/a.h', '/dir1/b.h', '/dir2/c.h'])
        >>> assert h.cpp_flags == '-I/dir1 -I/dir2'
        """
        return ' '.join(['-I' + x for x in self.directories])

    @property
    def macro_definitions(self):
        """Macro definitions

        >>> h = HeaderList(['/dir1/a.h', '/dir1/b.h', '/dir2/c.h'])
        >>> h.add_macro('-DBOOST_LIB_NAME=boost_regex')
        >>> h.add_macro('-DBOOST_DYN_LINK')
        >>> assert h.macro_definitions == '-DBOOST_LIB_NAME=boost_regex -DBOOST_DYN_LINK'  # noqa
        """
        return ' '.join(self._macro_definitions)

    @property
    def cpp_flags(self):
        """Include flags + macro definitions

        >>> h = HeaderList(['/dir1/a.h', '/dir1/b.h', '/dir2/c.h'])
        >>> h.add_macro('-DBOOST_DYN_LINK')
        >>> assert h.macro_definitions == '-I/dir1 -I/dir2 -DBOOST_DYN_LINK'
        """
        return self.include_flags + ' ' + self.macro_definitions

    def add_macro(self, macro):
        """Add a macro definition"""
        self._macro_definitions.append(macro)


def find_headers(headers, root, recurse=False):
    """Returns an iterable object containing a list of full paths to
    headers if found.

    Accepts any glob characters accepted by fnmatch:

    =======  ====================================
    Pattern  Meaning
    =======  ====================================
    *        matches everything
    ?        matches any single character
    [seq]    matches any character in ``seq``
    [!seq]   matches any character not in ``seq``
    =======  ====================================

    Parameters:
        headers (str or list of str): Header name(s) to search for
        root (str): The root directory to start searching from
        recurses (bool, optional): if False search only root folder,
            if True descends top-down from the root. Defaults to False.

    Returns:
        HeaderList: The headers that have been found
    """
    if isinstance(headers, six.string_types):
        headers = [headers]
    elif not isinstance(headers, collections.Sequence):
        message = '{0} expects a string or sequence of strings as the '
        message += 'first argument [got {1} instead]'
        message = message.format(find_headers.__name__, type(headers))
        raise TypeError(message)

    # Construct the right suffix for the headers
    suffix = 'h'

    # List of headers we are searching with suffixes
    headers = ['{0}.{1}'.format(header, suffix) for header in headers]

    return HeaderList(find(root, headers, recurse))


class LibraryList(FileList):
    """Sequence of absolute paths to libraries

    Provides a few convenience methods to manipulate library paths and get
    commonly used compiler flags or names
    """

    @property
    def libraries(self):
        return self.files

    @property
    def names(self):
        """Stable de-duplication of library names in the list

        >>> l = LibraryList(['/dir1/liba.a', '/dir2/libb.a', '/dir3/liba.so'])
        >>> assert l.names == ['a', 'b']
        """
        return list(dedupe(x.split('.')[0][3:] for x in self.basenames))

    @property
    def search_flags(self):
        """Search flags for the libraries

        >>> l = LibraryList(['/dir1/liba.a', '/dir2/libb.a', '/dir1/liba.so'])
        >>> assert l.search_flags == '-L/dir1 -L/dir2'
        """
        return ' '.join(['-L' + x for x in self.directories])

    @property
    def link_flags(self):
        """Link flags for the libraries

        >>> l = LibraryList(['/dir1/liba.a', '/dir2/libb.a', '/dir1/liba.so'])
        >>> assert l.search_flags == '-la -lb'
        """
        return ' '.join(['-l' + name for name in self.names])

    @property
    def ld_flags(self):
        """Search flags + link flags

        >>> l = LibraryList(['/dir1/liba.a', '/dir2/libb.a', '/dir1/liba.so'])
        >>> assert l.search_flags == '-L/dir1 -L/dir2 -la -lb'
        """
        return self.search_flags + ' ' + self.link_flags


def find_system_libraries(libraries, shared=True):
    """Searches the usual system library locations for ``libraries``.

    Search order is as follows:

    1. ``/lib64``
    2. ``/lib``
    3. ``/usr/lib64``
    4. ``/usr/lib``
    5. ``/usr/local/lib64``
    6. ``/usr/local/lib``

    Accepts any glob characters accepted by fnmatch:

    =======  ====================================
    Pattern  Meaning
    =======  ====================================
    *        matches everything
    ?        matches any single character
    [seq]    matches any character in ``seq``
    [!seq]   matches any character not in ``seq``
    =======  ====================================

    Parameters:
        libraries (str or list of str): Library name(s) to search for
        shared (bool, optional): if True searches for shared libraries,
            otherwise for static. Defaults to True.

    Returns:
        LibraryList: The libraries that have been found
    """
    if isinstance(libraries, six.string_types):
        libraries = [libraries]
    elif not isinstance(libraries, collections.Sequence):
        message = '{0} expects a string or sequence of strings as the '
        message += 'first argument [got {1} instead]'
        message = message.format(find_system_libraries.__name__,
                                 type(libraries))
        raise TypeError(message)

    libraries_found = []
    search_locations = [
        '/lib64',
        '/lib',
        '/usr/lib64',
        '/usr/lib',
        '/usr/local/lib64',
        '/usr/local/lib',
    ]

    for library in libraries:
        for root in search_locations:
            result = find_libraries(library, root, shared, recurse=True)
            if result:
                libraries_found += result
                break

    return libraries_found


def find_libraries(libraries, root, shared=True, recurse=False):
    """Returns an iterable of full paths to libraries found in a root dir.

    Accepts any glob characters accepted by fnmatch:

    =======  ====================================
    Pattern  Meaning
    =======  ====================================
    *        matches everything
    ?        matches any single character
    [seq]    matches any character in ``seq``
    [!seq]   matches any character not in ``seq``
    =======  ====================================

    Parameters:
        libraries (str or list of str): Library name(s) to search for
        root (str): The root directory to start searching from
        shared (bool, optional): if True searches for shared libraries,
            otherwise for static. Defaults to True.
        recurse (bool, optional): if False search only root folder,
            if True descends top-down from the root. Defaults to False.

    Returns:
        LibraryList: The libraries that have been found
    """
    if isinstance(libraries, six.string_types):
        libraries = [libraries]
    elif not isinstance(libraries, collections.Sequence):
        message = '{0} expects a string or sequence of strings as the '
        message += 'first argument [got {1} instead]'
        message = message.format(find_libraries.__name__, type(libraries))
        raise TypeError(message)

    # Construct the right suffix for the library
    if shared is True:
        suffix = 'dylib' if sys.platform == 'darwin' else 'so'
    else:
        suffix = 'a'
    # List of libraries we are searching with suffixes
    libraries = ['{0}.{1}'.format(lib, suffix) for lib in libraries]

    return LibraryList(find(root, libraries, recurse))
