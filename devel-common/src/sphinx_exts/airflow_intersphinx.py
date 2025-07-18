# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from provider_yaml_utils import load_package_data

if TYPE_CHECKING:
    from sphinx.application import Sphinx

AIRFLOW_ROOT_PATH = Path(os.path.abspath(__file__)).parents[3]
GENERATED_PATH = AIRFLOW_ROOT_PATH / "generated"


def _create_init_py(app, config):
    del app
    # del config
    intersphinx_mapping = getattr(config, "intersphinx_mapping", None) or {}

    providers_mapping = _generate_provider_intersphinx_mapping()
    intersphinx_mapping.update(providers_mapping)

    config.intersphinx_mapping = intersphinx_mapping


def _generate_provider_intersphinx_mapping() -> dict[str, tuple[str, tuple[str, ...]]]:
    airflow_mapping: dict[str, tuple[str, tuple[str, ...]]] = {}
    current_version = "stable"

    for provider in load_package_data():
        package_name: str = provider["package-name"]
        if os.environ.get("AIRFLOW_PACKAGE_NAME") == package_name:
            continue

        provider_base_url = f"/docs/{package_name}/{current_version}/"
        doc_inventory = GENERATED_PATH / "_build" / "docs" / package_name / current_version / "objects.inv"
        cache_inventory = GENERATED_PATH / "_inventory_cache" / package_name / "objects.inv"

        # Skip adding the mapping if the path does not exist
        if not os.path.exists(doc_inventory) and not os.path.exists(cache_inventory):
            continue

        airflow_mapping[package_name] = (
            # base URI
            provider_base_url,
            (doc_inventory.as_posix() if doc_inventory.exists() else cache_inventory.as_posix(),),
        )
    for pkg_name in ["apache-airflow", "helm-chart", "task-sdk"]:
        if os.environ.get("AIRFLOW_PACKAGE_NAME") == pkg_name:
            continue
        doc_inventory = GENERATED_PATH / "_build" / "docs" / pkg_name / current_version / "objects.inv"
        cache_inventory = GENERATED_PATH / "_inventory_cache" / pkg_name / "objects.inv"

        airflow_mapping[pkg_name] = (
            # base URI
            f"/docs/{pkg_name}/stable/",
            (doc_inventory.as_posix() if doc_inventory.exists() else cache_inventory.as_posix(),),
        )
    for pkg_name in ["apache-airflow-providers", "docker-stack"]:
        if os.environ.get("AIRFLOW_PACKAGE_NAME") == pkg_name:
            continue
        doc_inventory = GENERATED_PATH / "_build" / "docs" / pkg_name / "objects.inv"
        cache_inventory = GENERATED_PATH / "_inventory_cache" / pkg_name / "objects.inv"

        airflow_mapping[pkg_name] = (
            # base URI
            f"/docs/{pkg_name}/",
            (doc_inventory.as_posix() if doc_inventory.exists() else cache_inventory.as_posix(),),
        )
    return airflow_mapping


def setup(app: Sphinx):
    """Sets the plugin up"""
    app.connect("config-inited", _create_init_py)

    return {"version": "builtin", "parallel_read_safe": True, "parallel_write_safe": True}


if __name__ == "__main__":

    def main():
        """A simple application that displays the roles available for Airflow documentation."""
        import concurrent.futures
        import sys

        from sphinx.ext.intersphinx import fetch_inventory_group

        class _MockConfig:
            intersphinx_timeout = None
            intersphinx_cache_limit = 1
            tls_verify = False
            user_agent = None

        class _MockApp:
            srcdir = ""
            config = _MockConfig()

            def warn(self, msg: str) -> None:
                """Display warning"""
                print(msg, file=sys.stderr)

        def fetch_inventories(intersphinx_mapping) -> dict[str, Any]:
            print(f"Fetching inventories to: ${GENERATED_PATH}/_inventory_cache")
            now = int(time.time())

            cache: dict[Any, Any] = {}
            with concurrent.futures.ThreadPoolExecutor() as pool:
                for name, (uri, invs) in intersphinx_mapping.values():
                    pool.submit(fetch_inventory_group, name, uri, invs, cache, _MockApp(), now)  # type: ignore[arg-type]

            inv_dict = {}
            for uri, (name, now, invdata) in cache.items():
                del uri
                del now
                inv_dict[name] = invdata
            return inv_dict

        def domain_and_object_type_to_role(domain: str, object_type: str) -> str:
            if domain == "py":
                from sphinx.domains.python import PythonDomain

                role_name = PythonDomain.object_types[object_type].roles[0]
            elif domain == "std":
                from sphinx.domains.std import StandardDomain

                role_name = StandardDomain.object_types[object_type].roles[0]
            else:
                role_name = object_type
            return role_name

        def inspect_main(inv_data, name) -> None:
            try:
                for key in sorted(inv_data or {}):
                    domain, object_type = key.split(":")
                    role_name = domain_and_object_type_to_role(domain, object_type)
                    for entry in sorted(inv_data[key].keys()):
                        print(f":{role_name}:`{name}:{entry}`")
            except ValueError as exc:
                print(exc.args[0] % exc.args[1:])
            except Exception as exc:
                print(f"Unknown error: {exc!r}")

        provider_mapping = _generate_provider_intersphinx_mapping()

        for key, value in provider_mapping.copy().items():
            provider_mapping[key] = (key, value)

        inv_dict = fetch_inventories(provider_mapping)

        for name, inv_data in inv_dict.items():
            inspect_main(inv_data, name)

    import logging

    logging.basicConfig(level=logging.DEBUG)
    main()
