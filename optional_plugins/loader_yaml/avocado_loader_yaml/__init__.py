# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: Red Hat Inc. 2017
# Author: Lukas Doktor <ldoktor@redhat.com>
"""Avocado Plugin that loads tests from YAML files"""

import copy

from avocado.core import loader
from avocado.core import mux
from avocado.core import varianter
from avocado.core.plugin_interfaces import CLI
from avocado_varianter_yaml_to_mux import create_from_yaml


class YamlTestsuiteLoader(loader.TestLoader):

    """
    Gets variants from a YAML file and uses `test_reference` entries
    to create a test suite.
    """

    name = "yaml_testsuite"
    _extra_type_label_mapping = {}
    _extra_decorator_mapping = {}

    @staticmethod
    def get_type_label_mapping():
        """
        No type is discovered by default, uses "full_*_mappings" to report
        the actual types after "discover()" is called.
        """
        return {}

    def get_full_type_label_mapping(self):
        return self._extra_type_label_mapping

    @staticmethod
    def get_decorator_mapping():
        return {}

    def get_full_decorator_mapping(self):
        return self._extra_decorator_mapping

    def _get_loader(self, params):
        """
        Initializes test loader according to params.

        Uses params.get():
          test_reference_resolver_class - loadable location of the loader class
          test_reference_resolver_args - args to override current Avocado args
                                         before being passed to the loader
                                         class. (dict)
          test_reference_resolver_extra - extra_params to be passed to resolver
                                          (dict)
        """
        resolver_class = params.get("test_reference_resolver_class")
        if not resolver_class:
            if params.get("test_reference"):
                resolver_class = "avocado.core.loader.FileLoader"
            else:
                # Don't supply the default when no `test_reference` is given
                # to avoid listing default FileLoader tests
                return None
        mod, klass = resolver_class.rsplit(".", 1)
        try:
            loader_class = getattr(__import__(mod, fromlist=[klass]), klass)
        except ImportError:
            raise RuntimeError("Unable to import class defined by test_"
                               "reference_resolver_class '%s.%s'"
                               % (mod, klass))
        _args = params.get("test_reference_resolver_args")
        if not _args:
            args = self.args
        else:
            args = copy.deepcopy(self.args)
            for key, value in _args.iteritems():
                setattr(args, key, value)
        extra_params = params.get("test_reference_resolver_extra", default={})
        return loader_class(args, extra_params)

    def discover(self, reference, which_tests=loader.DEFAULT):
        tests = []
        try:
            root = mux.apply_filters(create_from_yaml([reference], False),
                                     getattr(self.args, "mux_suite_only", []),
                                     getattr(self.args, "mux_suite_out", []))
        except Exception:
            return []
        mux_tree = mux.MuxTree(root)
        for variant in mux_tree:
            params = varianter.AvocadoParams(variant, "YamlTestsuiteLoader",
                                             ["/run/*"], {})
            reference = params.get("test_reference")
            test_loader = self._get_loader(params)
            if not test_loader:
                continue
            _tests = test_loader.discover(reference, which_tests)
            self._extra_type_label_mapping.update(
                test_loader.get_full_type_label_mapping())
            self._extra_decorator_mapping.update(
                test_loader.get_full_decorator_mapping())
            if _tests:
                for tst in _tests:
                    tst[1]["params"] = (variant, ["/run/*"])
                tests.extend(_tests)
        return tests


class LoaderYAML(CLI):

    name = 'loader_yaml'
    description = "YAML test loader options for the 'run' subcommand"

    def configure(self, parser):
        for name in ("list", "run"):
            subparser = parser.subcommands.choices.get(name, None)
            if subparser is None:
                continue

        mux = subparser.add_argument_group("yaml to mux testsuite options")
        mux.add_argument("--mux-suite-only", nargs="+",
                         help="Filter only part of the YAML suite file")
        mux.add_argument("--mux-suite-out", nargs="+",
                         help="Filter out part of the YAML suite file")

    def run(self, args):
        loader.loader.register_plugin(YamlTestsuiteLoader)
