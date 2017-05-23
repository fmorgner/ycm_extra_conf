"""
A simple, dynamic configuration for YouCompleteMe's clang-completer

The variables in the section 'User configuration' allow you to customize paths
and flags for your project. You can also execute this script using the python
interpreter, to generate a generic list of flags for you project, which in turn
can be used by VIM color_coded for example.
"""

from os import path as op
import re
import subprocess
import sys

# User configuration:

# The language to use ('c' or 'c++')
LANG = 'c++'

# The language dialect ('iso' or 'gnu')
DIALECT = 'iso'

# The language standard version to use
# For C use either '89', '90', '99', or '11'
# For C++ use either '98', '03', '11', '14', or '1z' or '17'
STD = '1z'

# The project root directory
# Generally the default (the directoy where this script lies) is ok.
PROJECT_ROOT = op.abspath(op.dirname(__file__))

# The directory containing the 'conanbuildinfo.txt' file, if applicable
BUILDINFO_DIR = op.abspath(op.join(op.dirname(__file__), 'build'))

# General compiler flags (like warnings, etc.) to use during analysis
PROJECT_FLAGS = [
    '-Wall',
    '-Wextra',
    '-Werror',
    '-pedantic-errors',
]

# Project local include paths
# Relative paths will be resolved with regard to the PROJECT_ROOT
# NOTE: Do NOT use '-I' or other option flags, just simple paths
PROJECT_LOCAL_INCLUDES = [
    'include',
]

# Project external include paths
# Only absolute paths are applicable
# NOTE: Do NOT use '-I' or other option flags, just simple paths
PROJECT_EXTERNAL_INCLUDES = [
]

# Magic from here on out:

CLANG_REGEX = re.compile((
    r'(?:\#include \<...\> search starts here\:)'
    r'(?P<list>.*?)'
    r'(?:End of search list)'
), re.DOTALL)

STD = (LANG if DIALECT == 'iso' else
       (DIALECT if LANG == 'c' else DIALECT + '++')) + STD

CLANG_COMMAND = [
    'clang',
    '-v',
    '-E',
    '-x', LANG,
    '-std=' + STD,
    '-'
]


class ConanBuildInfo():
    """
    A simple parser for 'conanbuildinfo.txt' files
    """

    def __init__(self):
        path = op.abspath(op.join(BUILDINFO_DIR, 'conanbuildinfo.txt'))
        if not op.isfile(path):
            raise RuntimeError(
                'Could not find Conan build information at "%s"' % path
            )

        self._defines = []
        self._includedirs = []
        self._file = open(path, 'r')
        self._process = self._process_section
        self._do_parse()

    def _preprocess(self, line):
        if not line:
            return False
        elif line.startswith('['):
            self._process = self._process_section
        return True

    def _process_section(self, line):
        if line == '[includedirs]':
            self._process = self._process_includedir
        if line == '[defines]':
            self._process = self._process_define

    def _process_includedir(self, line):
        line = op.abspath(line)
        self._includedirs.append(line)

    def _process_define(self, line):
        self._defines.append(line)

    def _do_parse(self):
        for line in self._file:
            line = line.strip()
            if self._preprocess(line):
                self._process(line)

    @property
    def includes(self):
        """
        Access the include paths defined in the 'conanbuildinfo.txt' file
        """
        return self._includedirs

    @property
    def defines(self):
        """
        Access the preprocessor defines defined in the 'conanbuildinfo.txt'
        file
        """
        return self._defines


def compiler_includes():
    """
    Acquire clangs system include paths
    """
    process = subprocess.Popen(CLANG_COMMAND,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    process_out, process_err = process.communicate('')
    output = process_out + process_err
    output = str(output).encode('utf8').decode('unicode_escape')
    flags = []
    try:
        for path in re.search(CLANG_REGEX, output).group('list').split('\n'):
            path = path.strip()
            if path and path.find('(framework directory)') < 0:
                flags.append('-isystem')
                flags.append(op.abspath(path))
        return flags
    except AttributeError:
        print('Failed to acquire system includes from compiler')
        print('Tried with the following commandline:\n')
        print(' '.join(CLANG_COMMAND))
        sys.exit(1)


def project_local_includes():
    """
    Process the PROJECT_LOCAL_INCLUDES for delivery to the completer

    Makes sure that all paths are absolute.
    """
    paths = iter(PROJECT_LOCAL_INCLUDES)
    for path in paths:
        yield '-I'
        if not op.isabs(path):
            yield op.abspath(op.join(PROJECT_ROOT, path))
        else:
            yield path


def project_external_includes():
    """
    Process the PROJECT_EXTERNAL_INCLUDES for delivery to the completer

    Prevents relative paths.
    """
    paths = iter(PROJECT_EXTERNAL_INCLUDES)
    for path in paths:
        if not op.isabs(path):
            raise RuntimeError('Expected absolute path for external headers')
        yield '-I'
        yield op.abspath(path)


# pylint: disable=C0103
# pylint: disable=W0613
def FlagsForFile(filename, **kwargs):
    """
    Generate the compilation flags for the current file
    """
    flags = [
        '-x',
        LANG,
        '-std=' + STD,
    ]

    flags += PROJECT_FLAGS
    flags += compiler_includes()
    flags += project_local_includes()
    flags += project_external_includes()

    try:
        buildinfo = ConanBuildInfo()
        for path in buildinfo.includes:
            flags.append('-isystem')
            flags.append(path)
        for define in buildinfo.defines:
            flags.append('-D')
            flags.append(define)
    except RuntimeError:
        pass

    return {'flags': flags, 'do_cache': True}


if __name__ == '__main__':
    for flag in FlagsForFile(None)['flags']:
        print(flag)
