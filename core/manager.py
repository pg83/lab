import os
import shutil
import random

import core.j2 as cj
import core.vfs as cv
import core.error as er
import core.utils as cu
import core.realm as cr
import core.execute as ce
import core.package as cp


class Manager:
    def __init__(self, config):
        self._c = config
        self._p = {}
        self._e = cj.Env(cv.vfs(config.where))

    @property
    def env(self):
        return self._e

    @property
    def config(self):
        return self._c

    def load_file(self, path):
        with open(os.path.join(self.config.where, path)) as f:
            return f.read()

    def load_package(self, selector):
        key = cu.struct_hash(selector)

        while True:
            try:
                return self._p[key]
            except KeyError:
                print(selector)
                self._p[key] = cp.Package(selector, self)

    def iter_packages(self, selectors):
        def iter_deps():
            for sel in selectors:
                yield sel
                yield from self.load_package(sel).all_depends()

        for d in cu.iter_uniq_list(iter_deps()):
            yield self.load_package(d)

    def iter_runtime_packages(self, selectors):
        def iter_deps():
            for sel in selectors:
                yield sel
                yield from self.load_package(sel).all_runtime_depends()

        for d in cu.iter_uniq_list(iter_deps()):
            yield self.load_package(d)

    def iter_build_commands(self, selectors):
        for pkg in self.iter_packages(selectors):
            yield from pkg.commands()

    def build_graph(self, selectors):
        return {
            'nodes': list(self.iter_build_commands(selectors)),
            'targets': [self.load_package(x).out_dir + '/touch' for x in selectors],
        }

    # do not account flags
    def all_packages(self):
        for x in cu.iter_dir(self.config.where):
            if os.path.basename(x) in ('package.py', 'package.sh'):
                yield self.load_package({'name': os.path.dirname(x)})

    def build_packages(self, pkgs):
        tmp = os.path.join(self.config.store_dir, 'build.' + str(random.random()))

        try:
            shutil.move(self.config.build_dir, tmp)
        except FileNotFoundError:
            pass

        ce.execute(self.build_graph(pkgs))

    def load_realm(self, name):
        try:
            return cr.load_realm(self, name)
        except FileNotFoundError:
            raise er.Error(f'no such realm {name}')

    def prepare_realm(self, name, pkgs):
        return cr.prepare_realm(self, name, pkgs)

    def ensure_realm(self, name):
        try:
            return cr.load_realm(self, name)
        except FileNotFoundError as e:
            print(f'create new realm {name}')

        return self.prepare_realm(name, [])

    def iter_gc_candidates(self):
        yield self.config.build_dir

        p = self.config.store_dir

        for x in os.listdir(p):
            yield os.path.join(p, x)

    def list_realms(self):
        return os.listdir(self.config.realm_dir)

    def iter_used(self):
        for r in self.list_realms():
            rr = self.load_realm(r)

            yield rr.path
            yield from rr.links

    def iter_garbage(self):
        yield from sorted(frozenset(self.iter_gc_candidates()) - frozenset(self.iter_used()))
