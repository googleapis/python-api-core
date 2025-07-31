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

import sys
from unittest.mock import patch, MagicMock

import pytest
from packaging.version import parse as parse_version

from google.api_core._python_package_support import (
    get_dependency_version,
    warn_deprecation_for_versions_less_than,
)


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@patch("importlib.metadata.version")
def test_get_dependency_version_py38_plus(mock_version):
    """Test get_dependency_version on Python 3.8+."""
    mock_version.return_value = "1.2.3"
    assert get_dependency_version("some-package") == parse_version("1.2.3")
    mock_version.assert_called_once_with("some-package")

    # Test package not found
    mock_version.side_effect = ImportError
    assert get_dependency_version("not-a-package") is None


@pytest.mark.skipif(sys.version_info >= (3, 8), reason="requires python3.7")
@patch("pkg_resources.get_distribution")
def test_get_dependency_version_py37(mock_get_distribution):
    """Test get_dependency_version on Python 3.7."""
    mock_dist = MagicMock()
    mock_dist.version = "4.5.6"
    mock_get_distribution.return_value = mock_dist
    assert get_dependency_version("another-package") == parse_version("4.5.6")
    mock_get_distribution.assert_called_once_with("another-package")

    # Test package not found
    mock_get_distribution.side_effect = (
        Exception  # pkg_resources has its own exception types
    )
    assert get_dependency_version("not-a-package") is None


@patch("google.api_core._python_package_support._get_distribution_and_import_packages")
@patch("google.api_core._python_package_support.get_dependency_version")
@patch("google.api_core._python_package_support.logging.warning")
def test_warn_deprecation_for_versions_less_than(
    mock_log_warning, mock_get_version, mock_get_packages
):
    """Test the deprecation warning logic."""
    # Mock the helper function to return predictable package strings
    mock_get_packages.side_effect = [
        ("dep-package (dep.package)", "dep-package"),
        ("my-package (my.package)", "my-package"),
    ]

    # Case 1: Installed version is less than required, should warn.
    mock_get_version.return_value = parse_version("1.0.0")
    warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")
    mock_log_warning.assert_called_once()
    assert (
        "DEPRECATION: Package my-package (my.package) depends on dep-package (dep.package)"
        in mock_log_warning.call_args[0][0]
    )

    # Case 2: Installed version is equal to required, should not warn.
    mock_log_warning.reset_mock()
    mock_get_packages.reset_mock()
    mock_get_version.return_value = parse_version("2.0.0")
    warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")
    mock_log_warning.assert_not_called()

    # Case 3: Installed version is greater than required, should not warn.
    mock_log_warning.reset_mock()
    mock_get_packages.reset_mock()
    mock_get_version.return_value = parse_version("3.0.0")
    warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")
    mock_log_warning.assert_not_called()

    # Case 4: Dependency not found, should not warn.
    mock_log_warning.reset_mock()
    mock_get_packages.reset_mock()
    mock_get_version.return_value = None
    warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")
    mock_log_warning.assert_not_called()

    # Case 5: Custom message template.
    mock_log_warning.reset_mock()
    mock_get_packages.reset_mock()
    mock_get_packages.side_effect = [
        ("dep-package (dep.package)", "dep-package"),
        ("my-package (my.package)", "my-package"),
    ]
    mock_get_version.return_value = parse_version("1.0.0")
    template = "Custom warning for {dependency_packages} used by {dependent_packages}."
    warn_deprecation_for_versions_less_than(
        "my.package", "dep.package", "2.0.0", message_template=template
    )
    mock_log_warning.assert_called_once()
    assert (
        "Custom warning for dep-package (dep.package) used by my-package (my.package)."
        in mock_log_warning.call_args[0][0]
    )
