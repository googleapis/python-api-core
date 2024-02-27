# Copyright 2023 Google LLC
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

import pytest
from google.api_core import universe_helpers
from google.auth import credentials


def test__get_universe_domain():
    client_universe_domain = "foo.com"
    universe_domain_env = "bar.com"

    assert (
        universe_helpers._get_universe_domain(
            client_universe_domain, universe_domain_env
        )
        == client_universe_domain
    )
    assert (
        universe_helpers._get_universe_domain(None, universe_domain_env)
        == universe_domain_env
    )
    assert (
        universe_helpers._get_universe_domain(None, None)
        == universe_helpers._DEFAULT_UNIVERSE
    )

    with pytest.raises(ValueError) as excinfo:
        universe_helpers._get_universe_domain("", None)
    assert str(excinfo.value) == "Universe Domain cannot be an empty string."


def test__compare_universes():
    ga_credentials = credentials.AnonymousCredentials()
    mismatch_err_msg = (
        "The configured universe domain (foo.com) does not match the universe domain "
        "found in the credentials (googleapis.com). "
        "If you haven't configured the universe domain explicitly, "
        "`googleapis.com` is the default."
    )

    assert (
        universe_helpers._compare_universes(
            universe_helpers._DEFAULT_UNIVERSE, ga_credentials
        )
        is True
    )

    with pytest.raises(ValueError) as excinfo:
        universe_helpers._compare_universes("foo.com", ga_credentials)
    assert str(excinfo.value) == mismatch_err_msg
