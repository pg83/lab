#!/usr/bin/env python3

"""
The upstream libversion test table (tests/compare_test.c at 0789049),
row for row, minus the two rows upstream keeps commented out as
"controversial - TBD": (v1, v2, flags1, flags2, expected, symmetrical). Symmetrical
rows are also checked reversed with the flags swapped and the sign flipped,
as the C test does.
"""

import importlib.util
import sys
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location('libversion', Path(__file__).with_name('libversion.py'))
libversion = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = libversion
SPEC.loader.exec_module(libversion)

P_IS_PATCH = libversion.P_IS_PATCH
ANY_IS_PATCH = libversion.ANY_IS_PATCH
LOWER_BOUND = libversion.LOWER_BOUND
UPPER_BOUND = libversion.UPPER_BOUND


UPSTREAM = [
    ("0", "0", 0, 0, 0, True),
    ("0a", "0a", 0, 0, 0, True),
    ("a", "a", 0, 0, 0, True),
    ("a0", "a0", 0, 0, 0, True),
    ("0a1", "0a1", 0, 0, 0, True),
    ("0a1b2", "0a1b2", 0, 0, 0, True),
    ("1alpha1", "1alpha1", 0, 0, 0, True),
    ("foo", "foo", 0, 0, 0, True),
    ("1.2.3", "1.2.3", 0, 0, 0, True),
    ("hello.world", "hello.world", 0, 0, 0, True),
    ("1", "1.0", 0, 0, 0, True),
    ("1", "1.0.0", 0, 0, 0, True),
    ("1.0", "1.0.0", 0, 0, 0, True),
    ("1.0", "1.0.0.0.0.0.0.0", 0, 0, 0, True),
    ("00100.00100", "100.100", 0, 0, 0, True),
    ("0", "00000000000000000", 0, 0, 0, True),
    ("0.0.0", "0.0.1", 0, 0, -1, True),
    ("0.0.1", "0.0.2", 0, 0, -1, True),
    ("0.0.2", "0.0.10", 0, 0, -1, True),
    ("0.0.2", "0.1.0", 0, 0, -1, True),
    ("0.0.10", "0.1.0", 0, 0, -1, True),
    ("0.1.0", "0.1.1", 0, 0, -1, True),
    ("0.1.1", "1.0.0", 0, 0, -1, True),
    ("1.0.0", "10.0.0", 0, 0, -1, True),
    ("10.0.0", "100.0.0", 0, 0, -1, True),
    ("10.10000.10000", "11.0.0", 0, 0, -1, True),
    ("20160101", "20160102", 0, 0, -1, True),
    ("999999999999999999", "1000000000000000000", 0, 0, -1, True),
    ("99999999999999999999999999999999999998", "99999999999999999999999999999999999999", 0, 0, -1, True),
    ("1.0", "1.0a", 0, 0, -1, True),
    ("1.0a", "1.0b", 0, 0, -1, True),
    ("1.0b", "1.1", 0, 0, -1, True),
    ("a", "0", 0, 0, -1, True),
    ("1.a", "1.0", 0, 0, -1, True),
    ("1.0.a", "1.0.b", 0, 0, -1, True),
    ("1.0.b", "1.0.c", 0, 0, -1, True),
    ("1.0.c", "1.0", 0, 0, -1, True),
    ("1.0.c", "1.0.0", 0, 0, -1, True),
    ("1.0a0", "1.0.a0", 0, 0, 0, True),
    ("1.0beta3", "1.0.b3", 0, 0, 0, True),
    ("a", "A", 0, 0, 0, True),
    ("1alpha", "1ALPHA", 0, 0, 0, True),
    ("alpha1", "ALPHA1", 0, 0, 0, True),
    ("a", "alpha", 0, 0, 0, True),
    ("b", "beta", 0, 0, 0, True),
    ("p", "prerelease", 0, 0, 0, True),
    ("1.0.alpha.2", "1_0_alpha_2", 0, 0, 0, True),
    ("1.0.alpha.2", "1-0-alpha-2", 0, 0, 0, True),
    ("1.0.alpha.2", "1,0:alpha~2", 0, 0, 0, True),
    ("..1....2....3..", "1.2.3", 0, 0, 0, True),
    (".-~1~-.-~2~-.", "1.2", 0, 0, 0, True),
    (".,:;~+-_", "0", 0, 0, 0, True),
    ("", "", 0, 0, 0, True),
    ("", "0", 0, 0, 0, True),
    ("", "1", 0, 0, -1, True),
    ("1.0alpha1", "1.0alpha2", 0, 0, -1, True),
    ("1.0alpha2", "1.0beta1", 0, 0, -1, True),
    ("1.0beta1", "1.0beta2", 0, 0, -1, True),
    ("1.0beta2", "1.0rc1", 0, 0, -1, True),
    ("1.0beta2", "1.0pre1", 0, 0, -1, True),
    ("1.0rc1", "1.0", 0, 0, -1, True),
    ("1.0pre1", "1.0", 0, 0, -1, True),
    ("1.0.alpha1", "1.0.alpha2", 0, 0, -1, True),
    ("1.0.alpha2", "1.0.beta1", 0, 0, -1, True),
    ("1.0.beta1", "1.0.beta2", 0, 0, -1, True),
    ("1.0.beta2", "1.0.rc1", 0, 0, -1, True),
    ("1.0.beta2", "1.0.pre1", 0, 0, -1, True),
    ("1.0.rc1", "1.0", 0, 0, -1, True),
    ("1.0.pre1", "1.0", 0, 0, -1, True),
    ("1.0alpha.1", "1.0alpha.2", 0, 0, -1, True),
    ("1.0alpha.2", "1.0beta.1", 0, 0, -1, True),
    ("1.0beta.1", "1.0beta.2", 0, 0, -1, True),
    ("1.0beta.2", "1.0rc.1", 0, 0, -1, True),
    ("1.0beta.2", "1.0pre.1", 0, 0, -1, True),
    ("1.0rc.1", "1.0", 0, 0, -1, True),
    ("1.0pre.1", "1.0", 0, 0, -1, True),
    ("1.0.alpha.1", "1.0.alpha.2", 0, 0, -1, True),
    ("1.0.alpha.2", "1.0.beta.1", 0, 0, -1, True),
    ("1.0.beta.1", "1.0.beta.2", 0, 0, -1, True),
    ("1.0.beta.2", "1.0.rc.1", 0, 0, -1, True),
    ("1.0.beta.2", "1.0.pre.1", 0, 0, -1, True),
    ("1.0.rc.1", "1.0", 0, 0, -1, True),
    ("1.0.pre.1", "1.0", 0, 0, -1, True),
    ("1.0alpha-1", "0.9", 0, 0, 1, True),
    ("1.0alpha-1", "1.0", 0, 0, -1, True),
    ("1.0alpha-1", "1.0.1", 0, 0, -1, True),
    ("1.0alpha-1", "1.1", 0, 0, -1, True),
    ("1.0beta-1", "0.9", 0, 0, 1, True),
    ("1.0beta-1", "1.0", 0, 0, -1, True),
    ("1.0beta-1", "1.0.1", 0, 0, -1, True),
    ("1.0beta-1", "1.1", 0, 0, -1, True),
    ("1.0pre-1", "0.9", 0, 0, 1, True),
    ("1.0pre-1", "1.0", 0, 0, -1, True),
    ("1.0pre-1", "1.0.1", 0, 0, -1, True),
    ("1.0pre-1", "1.1", 0, 0, -1, True),
    ("1.0prerelease-1", "0.9", 0, 0, 1, True),
    ("1.0prerelease-1", "1.0", 0, 0, -1, True),
    ("1.0prerelease-1", "1.0.1", 0, 0, -1, True),
    ("1.0prerelease-1", "1.1", 0, 0, -1, True),
    ("1.0rc-1", "0.9", 0, 0, 1, True),
    ("1.0rc-1", "1.0", 0, 0, -1, True),
    ("1.0rc-1", "1.0.1", 0, 0, -1, True),
    ("1.0rc-1", "1.1", 0, 0, -1, True),
    ("1.0patch1", "0.9", 0, 0, 1, True),
    ("1.0patch1", "1.0", 0, 0, 1, True),
    ("1.0patch1", "1.0.1", 0, 0, -1, True),
    ("1.0patch1", "1.1", 0, 0, -1, True),
    ("1.0.patch1", "0.9", 0, 0, 1, True),
    ("1.0.patch1", "1.0", 0, 0, 1, True),
    ("1.0.patch1", "1.0.1", 0, 0, -1, True),
    ("1.0.patch1", "1.1", 0, 0, -1, True),
    ("1.0patch.1", "0.9", 0, 0, 1, True),
    ("1.0patch.1", "1.0", 0, 0, 1, True),
    ("1.0patch.1", "1.0.1", 0, 0, -1, True),
    ("1.0patch.1", "1.1", 0, 0, -1, True),
    ("1.0.patch.1", "0.9", 0, 0, 1, True),
    ("1.0.patch.1", "1.0", 0, 0, 1, True),
    ("1.0.patch.1", "1.0.1", 0, 0, -1, True),
    ("1.0.patch.1", "1.1", 0, 0, -1, True),
    ("1.0post1", "0.9", 0, 0, 1, True),
    ("1.0post1", "1.0", 0, 0, 1, True),
    ("1.0post1", "1.0.1", 0, 0, -1, True),
    ("1.0post1", "1.1", 0, 0, -1, True),
    ("1.0postanythinggoeshere1", "0.9", 0, 0, 1, True),
    ("1.0postanythinggoeshere1", "1.0", 0, 0, 1, True),
    ("1.0postanythinggoeshere1", "1.0.1", 0, 0, -1, True),
    ("1.0postanythinggoeshere1", "1.1", 0, 0, -1, True),
    ("1.0pl1", "0.9", 0, 0, 1, True),
    ("1.0pl1", "1.0", 0, 0, 1, True),
    ("1.0pl1", "1.0.1", 0, 0, -1, True),
    ("1.0pl1", "1.1", 0, 0, -1, True),
    ("1.0errata1", "0.9", 0, 0, 1, True),
    ("1.0errata1", "1.0", 0, 0, 1, True),
    ("1.0errata1", "1.0.1", 0, 0, -1, True),
    ("1.0errata1", "1.1", 0, 0, -1, True),
    ("1.0p1", "1.0p1", 0, 0, 0, True),
    ("1.0p1", "1.0p1", P_IS_PATCH, P_IS_PATCH, 0, True),
    ("1.0p1", "1.0p1", P_IS_PATCH, 0, 1, True),
    ("1.0p1", "1.0p1", 0, P_IS_PATCH, -1, True),
    ("1.0p1", "1.0P1", 0, 0, 0, True),
    ("1.0p1", "1.0P1", P_IS_PATCH, P_IS_PATCH, 0, True),
    ("1.0", "1.0p1", 0, 0, 1, True),
    ("1.0", "1.0p1", P_IS_PATCH, 0, 1, True),
    ("1.0", "1.0p1", 0, P_IS_PATCH, -1, True),
    ("1.0", "1.0.p1", 0, 0, 1, True),
    ("1.0", "1.0.p1", P_IS_PATCH, 0, 1, True),
    ("1.0", "1.0.p1", 0, P_IS_PATCH, -1, True),
    ("1.0", "1.0.p.1", 0, 0, 1, True),
    ("1.0", "1.0.p.1", P_IS_PATCH, 0, 1, True),
    ("1.0", "1.0.p.1", 0, P_IS_PATCH, -1, True),
    ("1.0", "1.0p.1", 0, 0, -1, True),
    ("1.0", "1.0p.1", P_IS_PATCH, 0, -1, True),
    ("1.0", "1.0p.1", 0, P_IS_PATCH, -1, True),
    ("1.0a1", "1.0a1", 0, 0, 0, True),
    ("1.0a1", "1.0a1", ANY_IS_PATCH, ANY_IS_PATCH, 0, True),
    ("1.0a1", "1.0a1", ANY_IS_PATCH, 0, 1, True),
    ("1.0a1", "1.0a1", 0, ANY_IS_PATCH, -1, True),
    ("1.0", "1.0a1", 0, 0, 1, True),
    ("1.0", "1.0a1", ANY_IS_PATCH, 0, 1, True),
    ("1.0", "1.0a1", 0, ANY_IS_PATCH, -1, True),
    ("1.0", "1.0.a1", 0, 0, 1, True),
    ("1.0", "1.0.a1", ANY_IS_PATCH, 0, 1, True),
    ("1.0", "1.0.a1", 0, ANY_IS_PATCH, -1, True),
    ("1.0", "1.0.a.1", 0, 0, 1, True),
    ("1.0", "1.0.a.1", ANY_IS_PATCH, 0, 1, True),
    ("1.0", "1.0.a.1", 0, ANY_IS_PATCH, -1, True),
    ("1.0", "1.0a.1", 0, 0, -1, True),
    ("1.0", "1.0a.1", ANY_IS_PATCH, 0, -1, True),
    ("1.0", "1.0a.1", 0, ANY_IS_PATCH, -1, True),
    ("1.0p1", "1.0pre1", 0, 0, 0, True),
    ("1.0p1", "1.0patch1", 0, 0, -1, True),
    ("1.0p1", "1.0post1", 0, 0, -1, True),
    ("1.0p1", "1.0pre1", P_IS_PATCH, P_IS_PATCH, 1, True),
    ("1.0p1", "1.0patch1", P_IS_PATCH, P_IS_PATCH, 0, True),
    ("1.0p1", "1.0post1", P_IS_PATCH, P_IS_PATCH, 0, True),
    ("1.0alpha", "1.0", 0, 0, -1, True),
    ("1.0.alpha", "1.0", 0, 0, -1, True),
    ("1.0beta", "1.0", 0, 0, -1, True),
    ("1.0.beta", "1.0", 0, 0, -1, True),
    ("1.0rc", "1.0", 0, 0, -1, True),
    ("1.0.rc", "1.0", 0, 0, -1, True),
    ("1.0pre", "1.0", 0, 0, -1, True),
    ("1.0.pre", "1.0", 0, 0, -1, True),
    ("1.0prerelese", "1.0", 0, 0, -1, True),
    ("1.0.prerelese", "1.0", 0, 0, -1, True),
    ("1.0patch", "1.0", 0, 0, 1, True),
    ("1.0.patch", "1.0", 0, 0, 1, True),
    ("0.99999", "1.0", 0, 0, -1, True),
    ("1.0alpha", "1.0", 0, 0, -1, True),
    ("1.0alpha0", "1.0", 0, 0, -1, True),
    ("1.0", "1.0", 0, 0, 0, True),
    ("1.0patch", "1.0", 0, 0, 1, True),
    ("1.0patch0", "1.0", 0, 0, 1, True),
    ("1.0.1", "1.0", 0, 0, 1, True),
    ("1.1", "1.0", 0, 0, 1, True),
    ("0.99999", "1.0", 0, LOWER_BOUND, -1, True),
    ("1.0alpha", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.0alpha0", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.0", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.0patch", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.0patch0", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.0a", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.0.1", "1.0", 0, LOWER_BOUND, 1, True),
    ("1.1", "1.0", 0, LOWER_BOUND, 1, True),
    ("0.99999", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0alpha", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0alpha0", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0patch", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0patch0", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0a", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.0.1", "1.0", 0, UPPER_BOUND, -1, True),
    ("1.1", "1.0", 0, UPPER_BOUND, 1, True),
    ("1.0", "1.0", LOWER_BOUND, LOWER_BOUND, 0, True),
    ("1.0", "1.0", UPPER_BOUND, UPPER_BOUND, 0, True),
    ("1.0", "1.0", LOWER_BOUND, UPPER_BOUND, -1, True),
    ("1.0", "1.1", UPPER_BOUND, LOWER_BOUND, -1, True),
    ("0", "0.0", UPPER_BOUND, UPPER_BOUND, 1, True),
    ("0", "0.0", LOWER_BOUND, LOWER_BOUND, -1, True),
    ("1.0alpha1", "1.0alpha1", 0, 0, 0, True),
    ("1.0alpha1", "1.0.alpha1", 0, 0, 0, True),
    ("1.0alpha1", "1.0alpha.1", 0, 0, 0, True),
    ("1.0alpha1", "1.0.alpha.1", 0, 0, 0, True),
    ("1.0patch1", "1.0patch1", 0, 0, 0, True),
    ("1.0patch1", "1.0.patch1", 0, 0, 0, True),
    ("1.0patch1", "1.0patch.1", 0, 0, 0, True),
    ("1.0patch1", "1.0.patch.1", 0, 0, 0, True),
]


class UpstreamTable(unittest.TestCase):
    def test_upstream_rows(self):
        self.assertEqual(len(UPSTREAM), 227)

        for v1, v2, f1, f2, expected, symmetrical in UPSTREAM:
            with self.subTest(v1=v1, v2=v2, f1=f1, f2=f2):
                self.assertEqual(libversion.version_compare(v1, v2, f1, f2), expected)

                if symmetrical:
                    self.assertEqual(libversion.version_compare(v2, v1, f2, f1), -expected)


class Parsing(unittest.TestCase):
    def test_components(self):
        self.assertEqual(
            libversion.parse('10.2alpha3..patch.4.'),
            [(4, 10), (4, 2), (1, 'a'), (4, 3), (3, 'p'), (4, 4)],
        )

    def test_letter_suffix_only_after_number_without_following_digit(self):
        self.assertEqual(libversion.parse('1.0a')[-1][0], 5)
        self.assertEqual(libversion.parse('1.0a.1')[2][0], 5)
        self.assertEqual(libversion.parse('1.0a1')[2][0], 1)
        self.assertEqual(libversion.parse('1.0.a')[2][0], 1)

    def test_non_ascii_is_a_separator(self):
        self.assertEqual(libversion.version_compare('1éé2', '1.2'), 0)
        self.assertEqual(libversion.version_compare('', '0.0.0'), 0)


if __name__ == '__main__':
    unittest.main()
