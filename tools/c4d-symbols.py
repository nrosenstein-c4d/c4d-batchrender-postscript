#!/usr/bin/env python
# coding: utf-8
#
# Copyright (C) 2012  Niklas Rosenstein
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
""" c4d-symbols - Tool for doing operations on a C4D-Symbols file
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ """

__author__ = 'Niklas Rosenstein <rosensteinniklas@gmail.com>'
__license__ = 'GNU GPL'

import os
import re
import sys
import errno
import argparse

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class CommandError(Exception):
    pass

def _build_argparser():
    parser = argparse.ArgumentParser(description='Tool for operating on a '
            'c4d_symbols.h file')
    parser.add_argument('mode', help='The mode to run the script in.',
            choices=['extract'])
    parser.add_argument('symbolsfile', help='The c4d_symbols.h file to '
            'operate on.', type=argparse.FileType())

    return parser

def extract(input, expr=re.compile('^\s*([\w_][\w\d_]*)\s*(=\s*(\d*))?,\s*$', re.M)):

    results = {}

    last_id = 0
    for line in input:
        match = expr.match(line)
        if not match:
            continue

        id = match.group(3)
        if id:
            id = int(id)
            last_id = id
        else:
            id = last_id + 1
            last_id = id

        results[match.group(1)] = id

    return results

def main():
    parser = _build_argparser()
    args = parser.parse_args()

    if args.mode == 'extract':
        dest_file = StringIO.StringIO()
        try:
            results = extract(args.symbolsfile)
        except CommandError as e:
            parser.error(e.message)

        print 'res = {'
        for k, v in sorted(results.iteritems(), key=lambda x: x[1]):
            print '    %r: %d,' % (k, v)
        print '}'
        return 0

    return errno.EAGAIN

if __name__ == '__main__':
    main()






