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
from ._python_version_support import (
    _flatten_message,
    _get_distribution_and_import_packages,
)

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
    dependent_import_package: str,
    dependency_import_package: str,
    next_supported_version: str,
    message_template: Optional[str] = None,
):
    """Issue any needed deprecation warnings for `dependency_import_package`.

    If `dependency_import_package` is installed at a version less than
    `next_supported_version`, this issues a warning using either a
    default `message_template` or one provided by the user. The
    default `message_template` informs the user that they will not receive
    future updates `dependent_import_package` if
    `dependency_import_package` is somehow pinned to a version lower
    than `next_supported_version`.

    Args:
      dependent_import_package: The import name of the package that
        needs `dependency_import_package`.
      dependency_import_package: The import name of the dependency to check.
      next_supported_version: The version number below which a deprecation
        warning will be logged.
      message_template: A custom default message template to replace
        the default. This `message_template` is treated as an
        f-string, where the following variables are defined:
        `dependency_import_package`, `dependent_import_package` and
        `dependency_package`, `dependent_package`, which contain both the
         import and distribution packages for the dependency and the dependent,
         respectively; and `next_supported_version` and `version_used`, which
         refer to supported and currently-used versions of the dependency.

    """
    if (
        not dependent_import_package
        or not dependency_import_package
        or not next_supported_version
    ):
        return
    version_used = get_dependency_version(dependency_import_package)
    if not version_used:
        return
    if version_used < parse_version(next_supported_version):
        (
            dependency_package,
            dependency_distribution_package,
        ) = _get_distribution_and_import_packages(dependency_import_package)
        (
            dependent_package,
            dependent_distribution_package,
        ) = _get_distribution_and_import_packages(dependent_import_package)
        message_template = message_template or _flatten_message(
            """
            DEPRECATION: Package {dependent_package} depends on
            {dependency_package}, currently installed at version
            {version_used.__str__}. Future updates to
            {dependent_package} will require {dependency_package} at
            version {next_supported_version} or higher. Please ensure
            that either (a) your Python environment doesn't pin the
            version of {dependency_package}, so that updates to
            {dependent_package} can require the higher version, or
            (b) you manually update your Python environment to use at
            least version {next_supported_version} of
            {dependency_package}.
            """
        )
        logging.warning(
            message_template.format(
                dependent_import_package=dependent_import_package,
                dependency_import_package=dependency_import_package,
                dependency_package=dependency_package,
                dependent_package=dependent_package,
                next_supported_version=next_supported_version,
                version_used=version_used,
            )
        )


def check_dependency_versions(dependent_import_package: str):
    """Bundle checks for all package dependencies.

    This function can be called by all dependents of google.api_core,
    to emit needed deprecation warnings for any of their
    dependencies. The dependencies to check should be updated here.

    Args:
      dependent_import_package: The distribution name of the calling package, whose
        dependencies we're checking.

    """
    warn_deprecation_for_versions_less_than(
        dependent_import_package, "google.protobuf", "4.25.8"
    )
