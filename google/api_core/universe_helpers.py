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

"""Helpers for universe domain."""

from google.auth.exceptions import MutualTLSChannelError
from typing import Any, Optional

_DEFAULT_UNIVERSE = "googleapis.com"

_mTLS_Universe_Error = MutualTLSChannelError(
    f"mTLS is not supported in any universe other than {_DEFAULT_UNIVERSE}."
)


class _UniverseMismatchError(ValueError):
    def __init__(self, client_universe, credentials_universe):
        message = (
            f"The configured universe domain ({client_universe}) does not match the universe domain "
            f"found in the credentials ({credentials_universe}). "
            "If you haven't configured the universe domain explicitly, "
            f"`{_DEFAULT_UNIVERSE}` is the default."
        )
        super().__init__(message)


def _get_universe_domain(
    client_universe_domain: Optional[str], universe_domain_env: Optional[str]
) -> str:
    """Return the universe domain used by the client.

    Args:
        client_universe_domain (Optional[str]): The universe domain configured via the client options.
        universe_domain_env (Optional[str]): The universe domain configured via the "GOOGLE_CLOUD_UNIVERSE_DOMAIN" environment variable.

    Returns:
        str: The universe domain to be used by the client.

    Raises:
        ValueError: If the universe domain is an empty string.
    """
    universe_domain = _DEFAULT_UNIVERSE
    if client_universe_domain is not None:
        universe_domain = client_universe_domain
    elif universe_domain_env is not None:
        universe_domain = universe_domain_env
    if len(universe_domain.strip()) == 0:
        raise ValueError("Universe Domain cannot be an empty string.")
    return universe_domain


def _compare_universes(client_universe: str, credentials: Any) -> bool:
    """Returns True iff the universe domains used by the client and credentials match.

    Args:
        client_universe (str): The universe domain configured via the client options.
        credentials Any: The credentials being used in the client.

    Returns:
        bool: True iff client_universe matches the universe in credentials.

    Raises:
        ValueError: when client_universe does not match the universe in credentials.
    """
    credentials_universe = getattr(credentials, "universe_domain", _DEFAULT_UNIVERSE)

    if client_universe != credentials_universe:
        raise _UniverseMismatchError(client_universe, credentials_universe)
    return True
