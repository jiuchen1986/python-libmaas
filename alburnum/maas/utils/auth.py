# Copyright 2012-2015 Canonical Ltd. Copyright 2015 Alburnum Ltd.
# This software is licensed under the GNU Affero General Public
# License version 3 (see the file LICENSE).

"""MAAS CLI authentication."""

__all__ = [
    "obtain_credentials",
    "obtain_password",
    "obtain_token",
    ]

from getpass import (
    getpass,
    getuser,
)
from socket import gethostname
import sys
from urllib.parse import urljoin

from alburnum.maas.utils.creds import Credentials
import bs4
import requests


def try_getpass(prompt):
    """Call `getpass`, ignoring EOF errors."""
    try:
        return getpass(prompt)
    except EOFError:
        return None


def obtain_credentials(credentials):
    """Prompt for credentials if possible.

    If the credentials are "-" then read from stdin without interactive
    prompting.
    """
    if credentials == "-":
        credentials = sys.stdin.readline().strip()
    elif credentials is None:
        credentials = try_getpass(
            "API key (leave empty for anonymous access): ")
    # Ensure that the credentials have a valid form.
    if credentials and not credentials.isspace():
        return Credentials.parse(credentials)
    else:
        return None


def obtain_password(password):
    """Prompt for password if possible.

    If the password is "-" then read from stdin without interactive prompting.
    """
    if password == "-":
        return sys.stdin.readline().strip()
    elif password is None:
        return try_getpass("Password: ")
    else:
        return password


def obtain_token(url, username, password):
    """Obtain a new API key by logging into MAAS.

    :return: A `Credentials` instance.
    """
    url_login = urljoin(url, "../../accounts/login/")
    url_token = urljoin(url, "account/")

    with requests.Session() as session:

        # Fetch the log-in page.
        response = session.get(url_login)
        response.raise_for_status()

        # Extract the CSRF token.
        login_doc = bs4.BeautifulSoup(response.content, "html.parser")
        login = login_doc.find('form', {"class": "login"})
        login_data = {
            elem["name"]: elem["value"] for elem in login("input")
            if elem.has_attr("name") and elem.has_attr("value")
        }
        login_data["username"] = username
        login_data["password"] = password
        # The following `requester` field is not used (at the time of
        # writing) but it ought to be associated with this new token so
        # that tokens can be selectively revoked a later date.
        login_data["requester"] = "%s@%s" % (getuser(), gethostname())

        # Log-in to MAAS.
        response = session.post(url_login, login_data)
        response.raise_for_status()

        # Request a new API token.
        response = session.post(
            url_token, {"op": "create_authorisation_token"},
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()

        # We have it!
        token = response.json()
        return Credentials(
            token["consumer_key"],
            token["token_key"],
            token["token_secret"],
        )