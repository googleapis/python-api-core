import pytest
from google.api_core import universe_helpers
from google.auth import credentials
from oauth2client import client


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
    assert str(excinfo.value) == str(universe_helpers._Empty_Universe_Error)


def test__compare_universes():
    ga_credentials = credentials.AnonymousCredentials()
    oauth2_credentials = client.GoogleCredentials(
        None, None, None, None, None, None, None, None
    )
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
    assert (
        universe_helpers._compare_universes(
            universe_helpers._DEFAULT_UNIVERSE, oauth2_credentials
        )
        is True
    )

    with pytest.raises(ValueError) as excinfo:
        universe_helpers._compare_universes("foo.com", ga_credentials)
    assert str(excinfo.value) == mismatch_err_msg

    with pytest.raises(ValueError) as excinfo:
        universe_helpers._compare_universes("foo.com", oauth2_credentials)
    assert str(excinfo.value) == mismatch_err_msg
