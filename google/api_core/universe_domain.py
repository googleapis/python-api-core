
GOOGLE_DEFAULT_UNIVERSE = "googleapis.com"

def _validate_universe_domain(client_universe, credentials_universe):
    """Validates the universe domain used by the client instance against
        the universe domain in the credentials.
    """
    if client_universe != credentials_universe:
        raise ValueError(f"The configured universe domain ({client_universe}) does not match the universe domain found in the credentials ({credentials_universe}). If you haven't configured the universe domain explicitly, `googleapis.com` is the default.")