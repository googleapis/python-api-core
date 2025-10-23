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
import warnings
from unittest.mock import patch, MagicMock

import pytest
from packaging.version import parse as parse_version

from google.api_core._python_package_support import (
    get_dependency_version,
    warn_deprecation_for_versions_less_than,
    DependencyVersion,
)


# TODO(https://github.com/googleapis/python-api-core/issues/835): Remove
# this mark once we drop support for Python 3.7
@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@patch("importlib.metadata.version")
def test_get_dependency_version_py38_plus(mock_version):
    """Test get_dependency_version on Python 3.8+."""
    mock_version.return_value = "1.2.3"
    expected = DependencyVersion(parse_version("1.2.3"), "1.2.3")
    assert get_dependency_version("some-package") == expected
    mock_version.assert_called_once_with("some-package")

    # Test package not found
    mock_version.side_effect = ImportError
    assert get_dependency_version("not-a-package") == DependencyVersion(None, "--")


# TODO(https://github.com/googleapis/python-api-core/issues/835): Remove
# this test function once we drop support for Python 3.7
@pytest.mark.skipif(sys.version_info >= (3, 8), reason="requires python3.7")
@patch("pkg_resources.get_distribution")
def test_get_dependency_version_py37(mock_get_distribution):
    """Test get_dependency_version on Python 3.7."""
    mock_dist = MagicMock()
    mock_dist.version = "4.5.6"
    mock_get_distribution.return_value = mock_dist
    expected = DependencyVersion(parse_version("4.5.6"), "4.5.6")
    assert get_dependency_version("another-package") == expected
    mock_get_distribution.assert_called_once_with("another-package")

    # Test package not found
    mock_get_distribution.side_effect = (
        Exception  # pkg_resources has its own exception types
    )
    assert get_dependency_version("not-a-package") == DependencyVersion(None, "--")


@patch("google.api_core._python_package_support._get_distribution_and_import_packages")
@patch("google.api_core._python_package_support.get_dependency_version")
def test_warn_deprecation_for_versions_less_than(mock_get_version, mock_get_packages):
    """Test the deprecation warning logic."""
    # Mock the helper function to return predictable package strings
    mock_get_packages.side_effect = [
        ("dep-package (dep.package)", "dep-package"),
        ("my-package (my.package)", "my-package"),
    ]

    mock_get_version.return_value = DependencyVersion(parse_version("1.0.0"), "1.0.0")
    with pytest.warns(FutureWarning) as record:
        warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")
    assert len(record) == 1
    assert (
        "DEPRECATION: Package my-package (my.package) depends on dep-package (dep.package)"
        in str(record[0].message)
    )

    # Cases where no warning should be issued
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")  # Capture all warnings

        # Case 2: Installed version is equal to required, should not warn.
        mock_get_packages.reset_mock()
        mock_get_version.return_value = DependencyVersion(
            parse_version("2.0.0"), "2.0.0"
        )
        warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")

        # Case 3: Installed version is greater than required, should not warn.
        mock_get_packages.reset_mock()
        mock_get_version.return_value = DependencyVersion(
            parse_version("3.0.0"), "3.0.0"
        )
        warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")

        # Case 4: Dependency not found, should not warn.
        mock_get_packages.reset_mock()
        mock_get_version.return_value = DependencyVersion(None, "--")
        warn_deprecation_for_versions_less_than("my.package", "dep.package", "2.0.0")

        # Assert that no warnings were recorded
        assert len(w) == 0

    # Case 5: Custom message template.
    mock_get_packages.reset_mock()
    mock_get_packages.side_effect = [
        ("dep-package (dep.package)", "dep-package"),
        ("my-package (my.package)", "my-package"),
    ]
    mock_get_version.return_value = DependencyVersion(parse_version("1.0.0"), "1.0.0")
    template = "Custom warning for {dependency_package} used by {consumer_package}."
    with pytest.warns(FutureWarning) as record:
        warn_deprecation_for_versions_less_than(
            "my.package", "dep.package", "2.0.0", message_template=template
        )
    assert len(record) == 1
    assert (
        "Custom warning for dep-package (dep.package) used by my-package (my.package)."
        in str(record[0].message)
    )


from google.api_core._python_package_support import (
    check_dependency_versions,
    DependencyConstraint,
)


@patch(
    "google.api_core._python_package_support.warn_deprecation_for_versions_less_than"
)
def test_check_dependency_versions_with_custom_warnings(mock_warn):
    """Test check_dependency_versions with custom warning parameters."""
    custom_warning1 = DependencyConstraint("pkg1", "1.0.0", "2.0.0")
    custom_warning2 = DependencyConstraint("pkg2", "2.0.0", "3.0.0")

    check_dependency_versions("my-consumer", custom_warning1, custom_warning2)

    assert mock_warn.call_count == 2
    mock_warn.assert_any_call(
        "my-consumer", "pkg1", "1.0.0", recommended_version="2.0.0"
    )
    mock_warn.assert_any_call(
        "my-consumer", "pkg2", "2.0.0", recommended_version="3.0.0"
    )
