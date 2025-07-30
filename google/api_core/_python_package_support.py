# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Code to check versions of dependencies used by Google Cloud Client Libraries."""

import logging
import sys
from typing import Optional
from ._python_version_support import _flatten_message

# It is a good practice to alias the Version class for clarity in type hints.
from packaging.version import parse as parse_version, Version as PackagingVersion


def get_dependency_version(dependency_name: str) -> Optional[PackagingVersion]:
    """Get the parsed version of an installed package dependency.

    This function checks for an installed package and returns its version
    as a `packaging.version.Version` object for safe comparison. It handles
    both modern (Python 3.8+) and legacy (Python 3.7) environments.

    Args:
        dependency_name: The distribution name of the package (e.g., 'requests').

    Returns:
        A `packaging.version.Version` object, or `None` if the package
        is not found or another error occurs during version discovery.
    """
    try:
        if sys.version_info >= (3, 8):
            from importlib import metadata

            version_string = metadata.version(dependency_name)
            return parse_version(version_string)

        # TODO: Remove this code path once we drop support for Python 3.7
        else:
            # Use pkg_resources, which is part of setuptools.
            import pkg_resources

            version_string = pkg_resources.get_distribution(dependency_name).version
            return parse_version(version_string)

    except Exception:
        return None


def warn_deprecation_for_versions_less_than(
    dependent_package: str,
    dependency_name: str,
    next_supported_version: str,
    message_template: Optional[str] = None,
):
    if not dependent_package or not dependency_name or not next_supported_version:
        return
    version_used = get_dependency_version(dependency_name)
    if not version_used:
        return
    if version_used < parse_version(next_supported_version):
        message_template = message_template or _flatten_message(
            """DEPRECATION: Package {dependent_package} depends on
            {dependency_name}, currently installed at version
            {version_used.__str__}. Future updates to
            {dependent_package} will require {dependency_name} at
            version {next_supported_version} or higher. Please ensure
            that either (a) your Python environment doesn't pin the
            version of {dependency_name}, so that updates to
            {dependent_package} can require the higher version, or (b)
            you manually update your Python environment to use at
            least version {next_supported_version} of
            {dependency_name}."""
        )
        logging.warning(
            message_template.format(
                dependent_package=dependent_package,
                dependency_name=dependency_name,
                next_supported_version=next_supported_version,
                version_used=version_used,
            )
        )


def check_dependency_versions(dependent_package: str):
    warn_deprecation_for_versions_less_than(
        dependent_package, "protobuf (google.protobuf)", "4.25.8"
    )
