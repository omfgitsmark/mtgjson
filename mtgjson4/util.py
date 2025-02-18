"""Utility functions."""
import contextvars
import hashlib
import json
import logging
import re
from typing import Any, Optional

import requests
import requests.adapters
import requests_cache
import urllib3.util.retry

import mtgjson4

LOGGER = logging.getLogger(__name__)
SESSION: contextvars.ContextVar = contextvars.ContextVar("SESSION")


def retryable_session(session: requests.Session, retries: int = 8) -> requests.Session:
    """
    Session with requests to allow for re-attempts at downloading missing data
    :param session: Session to download with
    :param retries: How many retries to attempt
    :return: Session that does downloading
    """
    retry = urllib3.util.retry.Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504),
    )

    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_generic_session() -> requests.Session:
    """Get or create a requests session for gatherer."""
    if mtgjson4.USE_CACHE.get():
        requests_cache.install_cache(
            str(mtgjson4.PROJECT_CACHE_PATH.joinpath("general_cache")),
            expire_after=mtgjson4.SESSION_CACHE_EXPIRE_GENERAL,
        )

    session: Optional[requests.Session] = SESSION.get(None)
    if not session:
        session = requests.Session()
        session = retryable_session(session)
        SESSION.set(session)

    return session


def is_number(string: str) -> bool:
    """See if a given string is a number (int or float)"""
    try:
        float(string)
        return True
    except ValueError:
        pass

    try:
        import unicodedata

        unicodedata.numeric(string)
        return True
    except (TypeError, ValueError):
        pass

    return False


def win_os_fix(set_name: str) -> str:
    """
    In the Windows OS, there are certain file names that are not allowed.
    In case we have a set with such a name, we will add a _ to the end to allow its existence
    on Windows.
    :param set_name: Set name
    :return: Set name with a _ if necessary
    """
    if set_name in mtgjson4.BANNED_FILE_NAMES:
        return set_name + "_"

    return set_name


def capital_case_without_symbols(name: str) -> str:
    """
    Determine the name of the output file by stripping
    all special characters and capital casing the words.
    :param name: Deck name (unsanitized)
    :return: Sanitized deck name
    """
    word_characters_only_regex = re.compile(r"[^\w]")
    capital_case = "".join(x for x in name.title() if not x.isspace())

    return word_characters_only_regex.sub("", capital_case)


def get_mtgjson_set_code(set_code: str) -> str:
    """
    Some set codes are wrong, so this will sanitize
    the set_code passed in
    :param set_code: Set code (unsanitized)
    :return: Sanitized set code
    """
    with mtgjson4.RESOURCE_PATH.joinpath("gatherer_set_codes.json").open(
        "r", encoding="utf-8"
    ) as f:
        json_dict = json.load(f)
        for key, value in json_dict.items():
            if set_code == value:
                return str(key)

    return set_code


def print_download_status(response: Any) -> None:
    """
    When a file is downloaded, this will log that response
    :param response: Response
    """
    cache_result: bool = response.from_cache if hasattr(
        response, "from_cache"
    ) else False
    LOGGER.info(f"Downloaded: {response.url} (Cache = {cache_result})")


def url_keygen(prod_id: int) -> str:
    """
    Generates a key that MTGJSON will use for redirection
    :param prod_id: Seed
    :return: URL Key
    """
    return hashlib.sha256(str(prod_id).encode()).hexdigest()[:16]
