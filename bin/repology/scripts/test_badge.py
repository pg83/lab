#!/usr/bin/env python3

"""
badge.py against repology-rs's own snapshots of /badge/repository-big
(repology-webapp/tests/snapshot_tests/snapshots at 4c05c91; fixture:
freebsd with 10 projects, 5 comparable, 1 newest, 2 outdated,
3 vulnerable, 4 problematic, 7 maintainers).
"""

import importlib.util
import sys
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location('badge', Path(__file__).with_name('badge.py'))
badge = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = badge
SPEC.loader.exec_module(badge)

FREEBSD = dict(projects=10, comparable=5, newest=1, outdated=2, vulnerable=3, problematic=4, maintainers=7)
EMPTY = dict(projects=0, comparable=0, newest=0, outdated=0, vulnerable=0, problematic=0, maintainers=0)

ACTIVE_REPOSITORY = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="159" height="145"><clipPath id="clip"><rect rx="3" wi'
    'dth="100%" height="100%" fill="#000"/></clipPath><linearGradient id="grad" x2="0" y2="100%"><stop of'
    'fset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><'
    'g clip-path="url(#clip)"><rect width="100%" height="100%" fill="#555"/><g fill="#fff" text-anchor="m'
    'iddle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="15" font-weight="bold"><text x'
    '="79" y="13" dominant-baseline="central" fill="#010101" fill-opacity=".3">Repository status</text><t'
    'ext x="79" y="12" dominant-baseline="central">Repository status</text></g><rect y="25" width="100%" '
    'height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" fo'
    'nt-size="11"><text x="80" y="36" text-anchor="end" dominant-baseline="central" fill="#010101" fill-o'
    'pacity=".3">Projects total</text><text x="80" y="35" text-anchor="end" dominant-baseline="central">P'
    'rojects total</text><text x="96" y="36" text-anchor="middle" dominant-baseline="central" fill="#0101'
    '01" fill-opacity=".3">10</text><text x="96" y="35" text-anchor="middle" dominant-baseline="central">'
    '10</text></g><rect x="85" y="45" width="23" height="20" fill="#4c1"/><rect x="108" y="45" width="51"'
    ' height="20" fill="#4c1"/><rect y="45" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" fo'
    'nt-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="80" y="56" text-anchor="en'
    'd" dominant-baseline="central" fill="#010101" fill-opacity=".3">Up to date</text><text x="80" y="55"'
    ' text-anchor="end" dominant-baseline="central">Up to date</text><text x="96" y="56" text-anchor="mid'
    'dle" dominant-baseline="central" fill="#010101" fill-opacity=".3">1</text><text x="96" y="55" text-a'
    'nchor="middle" dominant-baseline="central">1</text><text x="133" y="56" text-anchor="middle" dominan'
    't-baseline="central" fill="#010101" fill-opacity=".3">20.00%</text><text x="133" y="55" text-anchor='
    '"middle" dominant-baseline="central">20.00%</text></g><rect x="85" y="65" width="23" height="20" fil'
    'l="#e05d44"/><rect x="108" y="65" width="51" height="20" fill="#e05d44"/><rect y="65" width="100%" h'
    'eight="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" fon'
    't-size="11"><text x="80" y="76" text-anchor="end" dominant-baseline="central" fill="#010101" fill-op'
    'acity=".3">Outdated</text><text x="80" y="75" text-anchor="end" dominant-baseline="central">Outdated'
    '</text><text x="96" y="76" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opac'
    'ity=".3">2</text><text x="96" y="75" text-anchor="middle" dominant-baseline="central">2</text><text '
    'x="133" y="76" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">40.'
    '00%</text><text x="133" y="75" text-anchor="middle" dominant-baseline="central">40.00%</text></g><re'
    'ct x="85" y="85" width="23" height="20" fill="#e00000"/><rect x="108" y="85" width="51" height="20" '
    'fill="#e00000"/><rect y="85" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family='
    '"DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="80" y="96" text-anchor="end" dominan'
    't-baseline="central" fill="#010101" fill-opacity=".3">Vulnerable</text><text x="80" y="95" text-anch'
    'or="end" dominant-baseline="central">Vulnerable</text><text x="96" y="96" text-anchor="middle" domin'
    'ant-baseline="central" fill="#010101" fill-opacity=".3">3</text><text x="96" y="95" text-anchor="mid'
    'dle" dominant-baseline="central">3</text><text x="133" y="96" text-anchor="middle" dominant-baseline'
    '="central" fill="#010101" fill-opacity=".3">30.00%</text><text x="133" y="95" text-anchor="middle" d'
    'ominant-baseline="central">30.00%</text></g><rect x="85" y="105" width="23" height="20" fill="#9f9f9'
    'f"/><rect x="108" y="105" width="51" height="20" fill="#9f9f9f"/><rect y="105" width="100%" height="'
    '20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size='
    '"11"><text x="80" y="116" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacity='
    '".3">Bad versions</text><text x="80" y="115" text-anchor="end" dominant-baseline="central">Bad versi'
    'ons</text><text x="96" y="116" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-'
    'opacity=".3">4</text><text x="96" y="115" text-anchor="middle" dominant-baseline="central">4</text><'
    'text x="133" y="116" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".'
    '3">40.00%</text><text x="133" y="115" text-anchor="middle" dominant-baseline="central">40.00%</text>'
    '</g><rect y="125" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu San'
    's,Verdana,Geneva,sans-serif" font-size="11"><text x="80" y="136" text-anchor="end" dominant-baseline'
    '="central" fill="#010101" fill-opacity=".3">Maintainers</text><text x="80" y="135" text-anchor="end"'
    ' dominant-baseline="central">Maintainers</text><text x="96" y="136" text-anchor="middle" dominant-ba'
    'seline="central" fill="#010101" fill-opacity=".3">7</text><text x="96" y="135" text-anchor="middle" '
    'dominant-baseline="central">7</text></g></g></svg>'
)

HEADER_CUSTOM = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="156" height="145"><clipPath id="clip"><rect rx="3" wi'
    'dth="100%" height="100%" fill="#000"/></clipPath><linearGradient id="grad" x2="0" y2="100%"><stop of'
    'fset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><'
    'g clip-path="url(#clip)"><rect width="100%" height="100%" fill="#555"/><g fill="#fff" text-anchor="m'
    'iddle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="15" font-weight="bold"><text x'
    '="78" y="13" dominant-baseline="central" fill="#010101" fill-opacity=".3">FreeBSD</text><text x="78"'
    ' y="12" dominant-baseline="central">FreeBSD</text></g><rect y="25" width="100%" height="20" fill="ur'
    'l(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x'
    '="77" y="36" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacity=".3">Projects'
    ' total</text><text x="77" y="35" text-anchor="end" dominant-baseline="central">Projects total</text>'
    '<text x="93" y="36" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3'
    '">10</text><text x="93" y="35" text-anchor="middle" dominant-baseline="central">10</text></g><rect x'
    '="82" y="45" width="23" height="20" fill="#4c1"/><rect x="105" y="45" width="51" height="20" fill="#'
    '4c1"/><rect y="45" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sa'
    'ns,Verdana,Geneva,sans-serif" font-size="11"><text x="77" y="56" text-anchor="end" dominant-baseline'
    '="central" fill="#010101" fill-opacity=".3">Up to date</text><text x="77" y="55" text-anchor="end" d'
    'ominant-baseline="central">Up to date</text><text x="93" y="56" text-anchor="middle" dominant-baseli'
    'ne="central" fill="#010101" fill-opacity=".3">1</text><text x="93" y="55" text-anchor="middle" domin'
    'ant-baseline="central">1</text><text x="130" y="56" text-anchor="middle" dominant-baseline="central"'
    ' fill="#010101" fill-opacity=".3">20.00%</text><text x="130" y="55" text-anchor="middle" dominant-ba'
    'seline="central">20.00%</text></g><rect x="82" y="65" width="23" height="20" fill="#e05d44"/><rect x'
    '="105" y="65" width="51" height="20" fill="#e05d44"/><rect y="65" width="100%" height="20" fill="url'
    '(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x='
    '"77" y="76" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacity=".3">Outdated<'
    '/text><text x="77" y="75" text-anchor="end" dominant-baseline="central">Outdated</text><text x="93" '
    'y="76" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">2</text><te'
    'xt x="93" y="75" text-anchor="middle" dominant-baseline="central">2</text><text x="130" y="76" text-'
    'anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">40.00%</text><text x="1'
    '30" y="75" text-anchor="middle" dominant-baseline="central">40.00%</text></g><rect x="82" y="85" wid'
    'th="23" height="20" fill="#e00000"/><rect x="105" y="85" width="51" height="20" fill="#e00000"/><rec'
    't y="85" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana'
    ',Geneva,sans-serif" font-size="11"><text x="77" y="96" text-anchor="end" dominant-baseline="central"'
    ' fill="#010101" fill-opacity=".3">Vulnerable</text><text x="77" y="95" text-anchor="end" dominant-ba'
    'seline="central">Vulnerable</text><text x="93" y="96" text-anchor="middle" dominant-baseline="centra'
    'l" fill="#010101" fill-opacity=".3">3</text><text x="93" y="95" text-anchor="middle" dominant-baseli'
    'ne="central">3</text><text x="130" y="96" text-anchor="middle" dominant-baseline="central" fill="#01'
    '0101" fill-opacity=".3">30.00%</text><text x="130" y="95" text-anchor="middle" dominant-baseline="ce'
    'ntral">30.00%</text></g><rect x="82" y="105" width="23" height="20" fill="#9f9f9f"/><rect x="105" y='
    '"105" width="51" height="20" fill="#9f9f9f"/><rect y="105" width="100%" height="20" fill="url(#grad)'
    '"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="77" y='
    '"116" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacity=".3">Bad versions</t'
    'ext><text x="77" y="115" text-anchor="end" dominant-baseline="central">Bad versions</text><text x="9'
    '3" y="116" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">4</text'
    '><text x="93" y="115" text-anchor="middle" dominant-baseline="central">4</text><text x="130" y="116"'
    ' text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">40.00%</text><tex'
    't x="130" y="115" text-anchor="middle" dominant-baseline="central">40.00%</text></g><rect y="125" wi'
    'dth="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,san'
    's-serif" font-size="11"><text x="77" y="136" text-anchor="end" dominant-baseline="central" fill="#01'
    '0101" fill-opacity=".3">Maintainers</text><text x="77" y="135" text-anchor="end" dominant-baseline="'
    'central">Maintainers</text><text x="93" y="136" text-anchor="middle" dominant-baseline="central" fil'
    'l="#010101" fill-opacity=".3">7</text><text x="93" y="135" text-anchor="middle" dominant-baseline="c'
    'entral">7</text></g></g></svg>'
)

HEADER_EMPTY = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="156" height="120"><clipPath id="clip"><rect rx="3" wi'
    'dth="100%" height="100%" fill="#000"/></clipPath><linearGradient id="grad" x2="0" y2="100%"><stop of'
    'fset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><'
    'g clip-path="url(#clip)"><rect width="100%" height="100%" fill="#555"/><rect y="0" width="100%" heig'
    'ht="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-s'
    'ize="11"><text x="77" y="11" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opaci'
    'ty=".3">Projects total</text><text x="77" y="10" text-anchor="end" dominant-baseline="central">Proje'
    'cts total</text><text x="93" y="11" text-anchor="middle" dominant-baseline="central" fill="#010101" '
    'fill-opacity=".3">10</text><text x="93" y="10" text-anchor="middle" dominant-baseline="central">10</'
    'text></g><rect x="82" y="20" width="23" height="20" fill="#4c1"/><rect x="105" y="20" width="51" hei'
    'ght="20" fill="#4c1"/><rect y="20" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-f'
    'amily="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="77" y="31" text-anchor="end" d'
    'ominant-baseline="central" fill="#010101" fill-opacity=".3">Up to date</text><text x="77" y="30" tex'
    't-anchor="end" dominant-baseline="central">Up to date</text><text x="93" y="31" text-anchor="middle"'
    ' dominant-baseline="central" fill="#010101" fill-opacity=".3">1</text><text x="93" y="30" text-ancho'
    'r="middle" dominant-baseline="central">1</text><text x="130" y="31" text-anchor="middle" dominant-ba'
    'seline="central" fill="#010101" fill-opacity=".3">20.00%</text><text x="130" y="30" text-anchor="mid'
    'dle" dominant-baseline="central">20.00%</text></g><rect x="82" y="40" width="23" height="20" fill="#'
    'e05d44"/><rect x="105" y="40" width="51" height="20" fill="#e05d44"/><rect y="40" width="100%" heigh'
    't="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-si'
    'ze="11"><text x="77" y="51" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacit'
    'y=".3">Outdated</text><text x="77" y="50" text-anchor="end" dominant-baseline="central">Outdated</te'
    'xt><text x="93" y="51" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity='
    '".3">2</text><text x="93" y="50" text-anchor="middle" dominant-baseline="central">2</text><text x="1'
    '30" y="51" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">40.00%<'
    '/text><text x="130" y="50" text-anchor="middle" dominant-baseline="central">40.00%</text></g><rect x'
    '="82" y="60" width="23" height="20" fill="#e00000"/><rect x="105" y="60" width="51" height="20" fill'
    '="#e00000"/><rect y="60" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="Dej'
    'aVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="77" y="71" text-anchor="end" dominant-ba'
    'seline="central" fill="#010101" fill-opacity=".3">Vulnerable</text><text x="77" y="70" text-anchor="'
    'end" dominant-baseline="central">Vulnerable</text><text x="93" y="71" text-anchor="middle" dominant-'
    'baseline="central" fill="#010101" fill-opacity=".3">3</text><text x="93" y="70" text-anchor="middle"'
    ' dominant-baseline="central">3</text><text x="130" y="71" text-anchor="middle" dominant-baseline="ce'
    'ntral" fill="#010101" fill-opacity=".3">30.00%</text><text x="130" y="70" text-anchor="middle" domin'
    'ant-baseline="central">30.00%</text></g><rect x="82" y="80" width="23" height="20" fill="#9f9f9f"/><'
    'rect x="105" y="80" width="51" height="20" fill="#9f9f9f"/><rect y="80" width="100%" height="20" fil'
    'l="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><t'
    'ext x="77" y="91" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacity=".3">Bad'
    ' versions</text><text x="77" y="90" text-anchor="end" dominant-baseline="central">Bad versions</text'
    '><text x="93" y="91" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".'
    '3">4</text><text x="93" y="90" text-anchor="middle" dominant-baseline="central">4</text><text x="130'
    '" y="91" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">40.00%</t'
    'ext><text x="130" y="90" text-anchor="middle" dominant-baseline="central">40.00%</text></g><rect y="'
    '100" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Gen'
    'eva,sans-serif" font-size="11"><text x="77" y="111" text-anchor="end" dominant-baseline="central" fi'
    'll="#010101" fill-opacity=".3">Maintainers</text><text x="77" y="110" text-anchor="end" dominant-bas'
    'eline="central">Maintainers</text><text x="93" y="111" text-anchor="middle" dominant-baseline="centr'
    'al" fill="#010101" fill-opacity=".3">7</text><text x="93" y="110" text-anchor="middle" dominant-base'
    'line="central">7</text></g></g></svg>'
)

ACTIVE_REPOSITORY_WITHOUT_PACKAGES = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="159" height="125"><clipPath id="clip"><rect rx="3" wi'
    'dth="100%" height="100%" fill="#000"/></clipPath><linearGradient id="grad" x2="0" y2="100%"><stop of'
    'fset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><'
    'g clip-path="url(#clip)"><rect width="100%" height="100%" fill="#555"/><g fill="#fff" text-anchor="m'
    'iddle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="15" font-weight="bold"><text x'
    '="79" y="13" dominant-baseline="central" fill="#010101" fill-opacity=".3">Repository status</text><t'
    'ext x="79" y="12" dominant-baseline="central">Repository status</text></g><rect y="25" width="100%" '
    'height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" fo'
    'nt-size="11"><text x="125" y="36" text-anchor="end" dominant-baseline="central" fill="#010101" fill-'
    'opacity=".3">Projects total</text><text x="125" y="35" text-anchor="end" dominant-baseline="central"'
    '>Projects total</text><text x="138" y="36" text-anchor="middle" dominant-baseline="central" fill="#0'
    '10101" fill-opacity=".3">0</text><text x="138" y="35" text-anchor="middle" dominant-baseline="centra'
    'l">0</text></g><rect x="130" y="45" width="16" height="20" fill="#4c1"/><rect x="146" y="45" width="'
    '13" height="20" fill="#4c1"/><rect y="45" width="100%" height="20" fill="url(#grad)"/><g fill="#fff"'
    ' font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="125" y="56" text-anchor'
    '="end" dominant-baseline="central" fill="#010101" fill-opacity=".3">Up to date</text><text x="125" y'
    '="55" text-anchor="end" dominant-baseline="central">Up to date</text><text x="138" y="56" text-ancho'
    'r="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">0</text><text x="138" y="55"'
    ' text-anchor="middle" dominant-baseline="central">0</text><text x="152" y="56" text-anchor="middle" '
    'dominant-baseline="central" fill="#010101" fill-opacity=".3">-</text><text x="152" y="55" text-ancho'
    'r="middle" dominant-baseline="central">-</text></g><rect x="130" y="65" width="16" height="20" fill='
    '"#e05d44"/><rect x="146" y="65" width="13" height="20" fill="#e05d44"/><rect y="65" width="100%" hei'
    'ght="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-'
    'size="11"><text x="125" y="76" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opa'
    'city=".3">Outdated</text><text x="125" y="75" text-anchor="end" dominant-baseline="central">Outdated'
    '</text><text x="138" y="76" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opa'
    'city=".3">0</text><text x="138" y="75" text-anchor="middle" dominant-baseline="central">0</text><tex'
    't x="152" y="76" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">-'
    '</text><text x="152" y="75" text-anchor="middle" dominant-baseline="central">-</text></g><rect x="13'
    '0" y="85" width="16" height="20" fill="#e00000"/><rect x="146" y="85" width="13" height="20" fill="#'
    'e00000"/><rect y="85" width="100%" height="20" fill="url(#grad)"/><g fill="#fff" font-family="DejaVu'
    ' Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="125" y="96" text-anchor="end" dominant-base'
    'line="central" fill="#010101" fill-opacity=".3">Vulnerable</text><text x="125" y="95" text-anchor="e'
    'nd" dominant-baseline="central">Vulnerable</text><text x="138" y="96" text-anchor="middle" dominant-'
    'baseline="central" fill="#010101" fill-opacity=".3">0</text><text x="138" y="95" text-anchor="middle'
    '" dominant-baseline="central">0</text><text x="152" y="96" text-anchor="middle" dominant-baseline="c'
    'entral" fill="#010101" fill-opacity=".3">-</text><text x="152" y="95" text-anchor="middle" dominant-'
    'baseline="central">-</text></g><rect x="130" y="105" width="16" height="20" fill="#9f9f9f"/><rect x='
    '"146" y="105" width="13" height="20" fill="#9f9f9f"/><rect y="105" width="100%" height="20" fill="ur'
    'l(#grad)"/><g fill="#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x'
    '="125" y="116" text-anchor="end" dominant-baseline="central" fill="#010101" fill-opacity=".3">Bad ve'
    'rsions</text><text x="125" y="115" text-anchor="end" dominant-baseline="central">Bad versions</text>'
    '<text x="138" y="116" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity="'
    '.3">0</text><text x="138" y="115" text-anchor="middle" dominant-baseline="central">0</text><text x="'
    '152" y="116" text-anchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">-</te'
    'xt><text x="152" y="115" text-anchor="middle" dominant-baseline="central">-</text></g></g></svg>'
)

NONEXISTENT_REPOSITORY = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="222" height="45"><clipPath id="clip"><rect rx="3" wid'
    'th="100%" height="100%" fill="#000"/></clipPath><linearGradient id="grad" x2="0" y2="100%"><stop off'
    'set="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><g'
    ' clip-path="url(#clip)"><rect width="100%" height="100%" fill="#555"/><g fill="#fff" text-anchor="mi'
    'ddle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="15" font-weight="bold"><text x='
    '"111" y="13" dominant-baseline="central" fill="#010101" fill-opacity=".3">Repository status</text><t'
    'ext x="111" y="12" dominant-baseline="central">Repository status</text></g><rect x="0" y="25" width='
    '"222" height="20" fill="#e00000"/><rect y="25" width="100%" height="20" fill="url(#grad)"/><g fill="'
    '#fff" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11"><text x="111" y="36" text-a'
    'nchor="middle" dominant-baseline="central" fill="#010101" fill-opacity=".3">Repository not known or '
    'was removed</text><text x="111" y="35" text-anchor="middle" dominant-baseline="central">Repository n'
    'ot known or was removed</text></g></g></svg>'
)


class Snapshots(unittest.TestCase):
    def test_active_repository(self):
        self.assertEqual(badge.repository_big(FREEBSD), ACTIVE_REPOSITORY)

    def test_header_custom(self):
        self.assertEqual(badge.repository_big(FREEBSD, header='FreeBSD'), HEADER_CUSTOM)

    def test_header_empty(self):
        self.assertEqual(badge.repository_big(FREEBSD, header=None), HEADER_EMPTY)

    def test_active_repository_without_packages(self):
        self.assertEqual(badge.repository_big(EMPTY), ACTIVE_REPOSITORY_WITHOUT_PACKAGES)

    def test_unknown_repository(self):
        self.assertEqual(badge.repository_big(None), NONEXISTENT_REPOSITORY)


class Ours(unittest.TestCase):
    def test_without_vulnerable_count_the_row_is_left_out(self):
        stats = dict(FREEBSD)
        del stats['vulnerable']
        svg = badge.repository_big(stats)
        self.assertNotIn('Vulnerable', svg)
        self.assertIn('Bad versions', svg)
        self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="159" height="125">'))

    def test_text_width(self):
        # f32 sum of advance * size / 2048, truncated; 149 + 2 * 5 is the
        # 159 px width of their snapshots.
        self.assertEqual(badge.text_width('Projects total', 11), 72)
        self.assertEqual(badge.text_width('Repository status', 15, bold=True), 149)

        with self.assertRaises(ValueError):
            badge.text_width('\u00e9', 11)


if __name__ == '__main__':
    unittest.main()
