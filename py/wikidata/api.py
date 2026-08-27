#!/usr/bin/env python3
"""Talking to Wikidata: the query service for reads, the Action API for writes.

Standard library only, like the rest of this package -- no ``requests``, no
``pywikibot``. The client is deliberately narrow: it writes claims and
qualifiers and nothing else, and it cannot create items at all.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Wikidata's User-Agent policy expects a contact address. This placeholder is
# refused by the push step on purpose.
USER_AGENT = ("open-archaeo-wikidata/0.1 "
              "(https://github.com/n4o-rse/open-archaeo; contact: set in config.ini)")

# How many VALUES entries go into one WDQS query. The service accepts far more,
# but small batches keep an individual failure cheap to retry.
BATCH_SIZE = 100


class WikidataError(RuntimeError):
    """Any failure that came from the far end rather than from this code."""


def request(url: str, *, data: dict | None = None, headers: dict | None = None,
            opener=None, timeout: int = 60) -> str:
    """GET or POST and return the body, retrying transient failures twice."""
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    error: Exception | None = None
    for attempt in range(1, 4):
        req = urllib.request.Request(url, data=body, headers={
            "User-Agent": USER_AGENT, **(headers or {})})
        try:
            with (opener or urllib.request).urlopen(req, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                wait = 2.0 * attempt
                print(f"  transient HTTP {exc.code}, retrying in {wait}s",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise WikidataError(f"HTTP {exc.code} from {url}: {detail}") from None
        except urllib.error.URLError as exc:
            error = exc
            if attempt < 3:
                time.sleep(2.0 * attempt)
                continue
            raise WikidataError(f"cannot reach {url}: {exc.reason}") from None
        except (TimeoutError, OSError) as exc:
            # A read that stops mid-response raises socket.timeout, which is a
            # TimeoutError and *not* a URLError -- so without this branch a slow
            # query service escapes as a traceback rather than as a failure the
            # caller can decide about.
            error = exc
            if attempt < 3:
                wait = 2.0 * attempt
                print(f"  no answer in time, retrying in {wait}s",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            raise WikidataError(f"{url} did not answer in time: {exc}") from None
    raise WikidataError(f"giving up on {url}: {error}")


def sparql(query: str, *, endpoint: str = WDQS_ENDPOINT) -> list[dict]:
    """Run a SELECT against WDQS and return the bindings as flat dicts."""
    url = endpoint + "?" + urllib.parse.urlencode({"query": query})
    payload = json.loads(request(url, headers={
        "Accept": "application/sparql-results+json"}))
    return [{key: binding[key]["value"] for key in binding}
            for binding in payload["results"]["bindings"]]


def chunks(values: list, size: int = BATCH_SIZE):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def get_entities(ids: list[str], *, props: str = "info|datatype|labels|descriptions",
                 api_url: str = WIKIDATA_API) -> dict:
    """Read entities without authentication (wbgetentities is a public read)."""
    found: dict = {}
    for chunk in chunks(ids, 50):
        url = api_url + "?" + urllib.parse.urlencode({
            "action": "wbgetentities", "ids": "|".join(chunk),
            "props": props, "languages": "en|de", "format": "json"})
        found.update(json.loads(request(url)).get("entities", {}))
    return found


def search_entities(term: str, *, entity_type: str = "item", limit: int = 3,
                    api_url: str = WIKIDATA_API) -> list[dict]:
    url = api_url + "?" + urllib.parse.urlencode({
        "action": "wbsearchentities", "search": term, "language": "en",
        "uselang": "en", "type": entity_type, "limit": limit, "format": "json"})
    return json.loads(request(url)).get("search", [])


def value_payload(value, datatype: str):
    """The ``value`` argument of wbcreateclaim and wbsetqualifier."""
    if datatype == "item":
        return {"entity-type": "item", "numeric-id": int(value[1:])}
    if datatype == "time":
        return {"time": f"+{value}T00:00:00Z", "timezone": 0, "before": 0,
                "after": 0, "precision": 11,
                "calendarmodel": "http://www.wikidata.org/entity/Q1985727"}
    if datatype.startswith("monolingual"):
        _, _, language = datatype.partition("@")
        return {"text": value, "language": language or "en"}
    return value  # url, string and external-id are plain strings


# The entity JSON wbeditentity takes wants the datavalue *type*, which is not
# the property datatype: a url and an external-id are both carried as "string".
DATAVALUE_TYPES = {"item": "wikibase-entityid", "time": "time"}


def datavalue(value, datatype: str) -> dict:
    """One datavalue, as wbeditentity wants it inside an entity document."""
    kind = DATAVALUE_TYPES.get(datatype, "string")
    if datatype.startswith("monolingual"):
        kind = "monolingualtext"
    return {"value": value_payload(value, datatype), "type": kind}


def claim_document(claim) -> dict:
    """One statement with its qualifiers, as part of an entity document."""
    statement = {
        "mainsnak": {"snaktype": "value", "property": claim.prop,
                     "datavalue": datavalue(claim.value, claim.datatype)},
        "type": "statement", "rank": "normal",
    }
    if claim.qualifiers:
        qualifiers: dict[str, list] = {}
        for qualifier in claim.qualifiers:
            qualifiers.setdefault(qualifier.prop, []).append({
                "snaktype": "value", "property": qualifier.prop,
                "datavalue": datavalue(qualifier.value, qualifier.datatype)})
        statement["qualifiers"] = qualifiers
    return statement


def entity_document(label: str, description: str, claims: list) -> dict:
    """A whole new item: label, description and every statement at once.

    One edit rather than one per statement. That matters beyond speed: an item
    that is created and then has its class added in a second call exists, for a
    moment, as an untyped item with a name -- and if the run dies in between, it
    stays that way.
    """
    document = {"labels": {"en": {"language": "en", "value": label}},
                "claims": [claim_document(c) for c in claims]}
    if description:
        document["descriptions"] = {"en": {"language": "en",
                                           "value": description}}
    return document


class WikidataClient:
    """Login, tokens, and the two write calls.

    Follows the shape of ``wbqs/client.py`` in wikibase-federation -- login,
    CSRF token, wbcreateclaim, wbsetqualifier, retry on a stale token -- over
    urllib rather than requests.
    """

    def __init__(self, username: str, password: str, *,
                 api_url: str = WIKIDATA_API, user_agent: str = USER_AGENT,
                 throttle: float = 1.0, mark_bot: bool = False) -> None:
        self.api_url = api_url
        self.username = username
        self.password = password
        self.user_agent = user_agent
        self.throttle = throttle
        self.mark_bot = mark_bot
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(CookieJar()))
        self._csrf: str | None = None
        self._entities: dict[str, dict] = {}

    def call(self, params: dict, *, post: bool = False) -> dict:
        params = {"format": "json", **params}
        headers = {"User-Agent": self.user_agent}
        if post:
            raw = request(self.api_url, data=params, opener=self.opener,
                          headers=headers)
        else:
            raw = request(self.api_url + "?" + urllib.parse.urlencode(params),
                          opener=self.opener, headers=headers)
        result = json.loads(raw)
        if "error" in result:
            err = result["error"]
            raise WikidataError(f"API error [{err.get('code')}]: {err.get('info')}")
        return result

    def login(self) -> str:
        token = self.call({"action": "query", "meta": "tokens",
                           "type": "login"})["query"]["tokens"]["logintoken"]
        result = self.call({"action": "login", "lgname": self.username,
                            "lgpassword": self.password, "lgtoken": token},
                           post=True)
        if result.get("login", {}).get("result") != "Success":
            raise WikidataError(
                "login failed: " + json.dumps(result.get("login", result))
                + "\nHint: use a bot password (Special:BotPasswords); the "
                  "username then looks like 'Account@botname'.")
        return result["login"].get("lgusername", self.username)

    def whoami(self) -> dict:
        """Who the session is and what rights it has. Reads nothing else."""
        return self.call({"action": "query", "meta": "userinfo",
                          "uiprop": "rights|groups"})["query"]["userinfo"]

    def csrf(self, *, force: bool = False) -> str:
        if self._csrf is None or force:
            self._csrf = self.call({"action": "query", "meta": "tokens"}
                                   )["query"]["tokens"]["csrftoken"]
        return self._csrf

    def entity(self, qid: str) -> dict:
        if qid not in self._entities:
            result = self.call({"action": "wbgetentities", "ids": qid})
            self._entities[qid] = result.get("entities", {}).get(qid, {})
        return self._entities[qid]

    def claim_exists(self, qid: str, claim) -> bool:
        """True if this exact property/value pair is already on the item."""
        wanted = value_payload(claim.value, claim.datatype)
        for existing in self.entity(qid).get("claims", {}).get(claim.prop, []):
            value = existing.get("mainsnak", {}).get("datavalue", {}).get("value")
            if claim.datatype == "item":
                if isinstance(value, dict) and value.get("id") == claim.value:
                    return True
            elif claim.datatype == "time":
                if isinstance(value, dict) and \
                        value.get("time", "").startswith(f"+{claim.value}"):
                    return True
            elif claim.datatype.startswith("monolingual"):
                if isinstance(value, dict) and value.get("text") == wanted["text"] \
                        and value.get("language") == wanted["language"]:
                    return True
            elif value == wanted:
                return True
        return False

    def create_claim(self, qid: str, claim) -> str:
        for attempt in range(1, 4):
            try:
                result = self.call({
                    "action": "wbcreateclaim", "entity": qid,
                    "property": claim.prop, "snaktype": "value",
                    "value": json.dumps(value_payload(claim.value, claim.datatype),
                                        ensure_ascii=False),
                    "token": self.csrf(), "assert": "user",
                    **({"bot": "1"} if self.mark_bot else {})}, post=True)
            except WikidataError as exc:
                if "badtoken" in str(exc) and attempt < 3:
                    self.csrf(force=True)
                    continue
                raise
            self._entities.pop(qid, None)
            if self.throttle:
                time.sleep(self.throttle)
            return result["claim"]["id"]
        raise WikidataError("wbcreateclaim: retries exhausted")

    def create_item(self, label: str, description: str, claims: list) -> str:
        """Create an item and return its Q-id. The one call here that writes
        something that did not exist before, so it is deliberately separate
        from create_claim rather than a mode of it.
        """
        result = self.call({
            "action": "wbeditentity", "new": "item",
            "data": json.dumps(entity_document(label, description, claims),
                               ensure_ascii=False),
            "token": self.csrf(), "assert": "user",
            "summary": "create item from open-archaeo",
            **({"bot": "1"} if self.mark_bot else {})}, post=True)
        if self.throttle:
            time.sleep(self.throttle)
        return result["entity"]["id"]

    def add_qualifier(self, claim_id: str, qualifier) -> None:
        self.call({
            "action": "wbsetqualifier", "claim": claim_id,
            "property": qualifier.prop, "snaktype": "value",
            "value": json.dumps(value_payload(qualifier.value, qualifier.datatype),
                                ensure_ascii=False),
            "token": self.csrf(), "assert": "user",
            **({"bot": "1"} if self.mark_bot else {})}, post=True)
        if self.throttle:
            time.sleep(self.throttle)


def read_credentials(path: Path) -> tuple[str, str, str, float]:
    """Read config.ini. Environment variables win, as in wikibase-federation."""
    import configparser
    import os

    config = configparser.ConfigParser()
    if path.is_file():
        config.read(path, encoding="utf-8")
    username = (os.environ.get("WIKIDATA_USERNAME")
                or config.get("wikidata", "username", fallback="").strip())
    password = (os.environ.get("WIKIDATA_PASSWORD")
                or config.get("wikidata", "password", fallback=""))
    agent = config.get("wikidata", "user_agent", fallback=USER_AGENT).strip()
    throttle = config.getfloat("wikidata", "throttle_seconds", fallback=1.0)
    return username, password, agent or USER_AGENT, throttle
