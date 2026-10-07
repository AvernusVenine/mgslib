"""Talk to the MGS data server.  The only code that touches the network.

What the server is expected to do
---------------------------------
One request::

    POST {server}/data
    {"include": {"cwi": ["c5st", "c5ix"], "qdi": ["qdi"]},
     "by": {"county": ["Ramsey"]}}

``by`` values are always sent as lists, even when there is only one.

The answer holds each table as it is in the dataset, with its own column
names; ``schema.py`` works out what the columns mean::

    {"tables": {"cwi.c5ix": {"columns": ["RELATEID", ...], "rows": [[...], ...]},
                "cwi.c5st": {...},
                "qdi.qdi": {...}}}

On an error the server answers with a 4xx/5xx status and
``{"detail": "what went wrong"}`` (the FastAPI default), which is shown to the
user as it is.
"""

from __future__ import annotations

import os

import pandas as pd
import requests

SERVER_VARIABLE = "MGSLIB_DATA_URL"
DEFAULT_SERVER = None   # TODO: the address of the MGS data server, once it exists
TIMEOUT_SECONDS = 300

_server = None


def set_server(url) -> None:
    """Say where the MGS data server is, e.g. ``set_server("http://mgs-data:8000")``.

    Only needed if the address is not already set up on this computer.
    """
    global _server
    _server = str(url).strip() if url else None


def server_url() -> str:
    url = _server or os.environ.get(SERVER_VARIABLE) or DEFAULT_SERVER
    if not url:
        raise ConnectionError(
            "The address of the MGS data server is not set. Set it with "
            'set_server("http://..."), which is imported from mgslib.data.')
    return url.rstrip("/")


def fetch(include, by) -> dict:
    """Ask the server for tables.  Returns ``{"cwi.c5ix": DataFrame, ...}``."""
    url = server_url()
    try:
        response = requests.post(f"{url}/data", json={"include": include, "by": by},
                                 timeout=TIMEOUT_SECONDS)
    except requests.Timeout:
        raise ConnectionError(
            f"The MGS data server at {url} took too long to answer. "
            "Try asking for less data at once.") from None
    except requests.ConnectionError:
        raise ConnectionError(
            f"Could not reach the MGS data server at {url}. "
            "Check that you are on the MGS network.") from None
    if not response.ok:
        raise ValueError(f"The MGS data server could not answer: {_error_detail(response)}")
    return read_tables(response.json())


def _error_detail(response) -> str:
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    return str(detail) if detail else f"error {response.status_code}"


def read_tables(payload) -> dict:
    """Turn the server's answer into one DataFrame per table.

    The wire format lives here alone, so it can change (to Parquet, say)
    without touching anything else.
    """
    return {name: pd.DataFrame(table["rows"], columns=table["columns"])
            for name, table in payload["tables"].items()}
