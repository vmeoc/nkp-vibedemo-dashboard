"""The platform contract: what an application may ask from the NKP platform.

The contract file (contract.yaml in the app repo) is deliberately FLAT
("key: value" per line), so it can be read without any YAML library, both on
the laptop and in the GitHub runner.

validate() returns (normalized_contract, errors). An empty error list means
the platform accepts the contract.
"""

from __future__ import annotations

import datetime
import re

ENVS = {
    "dev": {"label": "Development", "default_replicas": 1},
    "test": {"label": "Test", "default_replicas": 1},
    "preprod": {"label": "Pre-production", "default_replicas": 2},
    "prod": {"label": "Production", "default_replicas": 2},
}

ARCHIS = {
    "stateless": {"label": "Stateless (no persistent volume)", "supported": True},
    "backend-db": {"label": "Backend + new database", "supported": False},
    "backend-db-existing": {"label": "Backend + existing database", "supported": False},
}

SIZES = {
    "S": {"label": "Small", "requests": {"cpu": "100m", "memory": "128Mi"},
          "limits": {"cpu": "500m", "memory": "256Mi"}},
    "M": {"label": "Medium", "requests": {"cpu": "250m", "memory": "256Mi"},
          "limits": {"cpu": "1", "memory": "512Mi"}},
    "L": {"label": "Large", "requests": {"cpu": "500m", "memory": "512Mi"},
          "limits": {"cpu": "2", "memory": "1Gi"}},
}

PROTECTIONS = {
    "none": "No backup - Git is enough for a stateless app (RPO: last commit)",
    "daily": "Daily backup at 02:00, 7 days retention (RPO 24h)",
    "hourly": "Hourly backup, 48 hours retention (RPO 1h)",
}

FIELDS = (
    "app", "owner", "cost_center", "env", "archi", "port",
    "replicas", "size", "protection", "tracing", "expires",
)
REQUIRED = ("app", "owner", "env", "archi", "port", "size", "protection")

DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
LABEL_VALUE = re.compile(r"^[A-Za-z0-9]([-A-Za-z0-9_.]*[A-Za-z0-9])?$")
LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
INT = re.compile(r"^-?[0-9]+$")


class ContractSyntaxError(ValueError):
    pass


# --------------------------------------------------------------------- parsing
def _strip_comment(value: str) -> str:
    """Remove a trailing ' # comment' that is outside quotes."""
    quote = None
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1] in " \t"):
            return value[:i].rstrip()
    return value.strip()


def _scalar(value: str):
    if value == "" or value in ("~", "null", "Null", "NULL"):
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        inner = value[1:-1]
        return inner if inner != "" else None
    if value in ("true", "True", "TRUE", "yes", "Yes"):
        return True
    if value in ("false", "False", "FALSE", "no", "No"):
        return False
    if INT.match(value):
        return int(value)
    return value


def parse(text: str) -> dict:
    """Parse a flat 'key: value' document. Raises ContractSyntaxError."""
    data = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#") or raw.strip() == "---":
            continue
        if raw[0] in " \t":
            raise ContractSyntaxError(
                "line %d: the contract must be flat (one 'key: value' per line, "
                "no indentation)" % number)
        match = LINE.match(raw.rstrip())
        if not match:
            raise ContractSyntaxError("line %d: expected 'key: value', got %r" % (number, raw))
        key, value = match.group(1), _strip_comment(match.group(2))
        if key in data:
            raise ContractSyntaxError("line %d: duplicate field %r" % (number, key))
        data[key] = _scalar(value)
    return data


# ------------------------------------------------------------------ validation
def validate(data: dict, today: datetime.date | None = None):
    """Return (normalized, errors). normalized is only meaningful without errors."""
    errors = []
    out = {}

    for key in data:
        if key not in FIELDS:
            errors.append("unknown field %r (allowed: %s)" % (key, ", ".join(FIELDS)))
    for key in REQUIRED:
        if data.get(key) is None:
            errors.append("field %r is required" % key)

    app = data.get("app")
    if app is not None:
        app = str(app)
        if len(app) > 40 or not DNS_LABEL.match(app):
            errors.append("app %r: lowercase letters, digits and dashes only, "
                          "must start and end with a letter or digit, 40 characters max" % app)
        out["app"] = app

    for key in ("owner", "cost_center"):
        value = data.get(key)
        if value is None:
            out[key] = None
            continue
        value = str(value)
        if len(value) > 63 or not LABEL_VALUE.match(value):
            errors.append("%s %r: must be usable as a Kubernetes label value "
                          "(letters, digits, '-', '_', '.', 63 characters max, no '@' or spaces)"
                          % (key, value))
        out[key] = value

    env = data.get("env")
    if env is not None and env not in ENVS:
        errors.append("env %r: must be one of %s" % (env, ", ".join(ENVS)))
    out["env"] = env

    archi = data.get("archi")
    if archi is not None:
        if archi not in ARCHIS:
            errors.append("archi %r: must be one of %s" % (archi, ", ".join(ARCHIS)))
        elif not ARCHIS[archi]["supported"]:
            errors.append("archi %r (%s) is not supported by the platform yet - "
                          "only 'stateless' is available today" % (archi, ARCHIS[archi]["label"]))
    out["archi"] = archi

    port = data.get("port")
    if port is not None and (not isinstance(port, int) or isinstance(port, bool)
                             or not 1 <= port <= 65535):
        errors.append("port %r: must be an integer between 1 and 65535" % (port,))
    out["port"] = port

    replicas = data.get("replicas")
    if replicas is not None and (not isinstance(replicas, int) or isinstance(replicas, bool)
                                 or replicas < 1 or replicas > 10):
        errors.append("replicas %r: must be an integer between 1 and 10" % (replicas,))
        replicas = None
    if replicas is None and env in ENVS:
        replicas = ENVS[env]["default_replicas"]
    out["replicas"] = replicas

    size = data.get("size")
    if size is not None:
        size = str(size).upper()
        if size not in SIZES:
            errors.append("size %r: must be one of S, M, L" % data.get("size"))
    out["size"] = size

    protection = data.get("protection")
    if protection is not None and protection not in PROTECTIONS:
        errors.append("protection %r: must be one of %s" % (protection, ", ".join(PROTECTIONS)))
    out["protection"] = protection

    tracing = data.get("tracing")
    if tracing is None:
        tracing = False
    if not isinstance(tracing, bool):
        errors.append("tracing %r: must be true or false" % (tracing,))
    out["tracing"] = tracing

    expires = data.get("expires")
    if expires is not None:
        expires = str(expires)
        try:
            datetime.date.fromisoformat(expires)
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", expires):
                raise ValueError
        except ValueError:
            errors.append("expires %r: must be a date in format YYYY-MM-DD" % expires)
    out["expires"] = expires

    # Environment-specific rules
    if env == "prod":
        if not out.get("cost_center"):
            errors.append("cost_center is mandatory in prod")
        if expires:
            errors.append("expires is forbidden in prod (a production app does not expire)")
        if isinstance(out.get("replicas"), int) and out["replicas"] < 2:
            errors.append("prod requires at least 2 replicas")

    return out, errors


def load(path) -> tuple:
    """Read + parse + validate a contract file. Returns (normalized, errors)."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    try:
        data = parse(text)
    except ContractSyntaxError as exc:
        return {}, [str(exc)]
    return validate(data)


def describe(c: dict) -> list:
    """Plain-English summary lines, for the AI to read back to the user."""
    size = SIZES.get(c.get("size") or "", {})
    lines = [
        "Application name : %s" % c.get("app"),
        "Owner            : %s" % c.get("owner"),
        "Cost center      : %s" % (c.get("cost_center") or "-"),
        "Environment      : %s (%s)" % (c.get("env"), ENVS.get(c.get("env"), {}).get("label", "?")),
        "Architecture     : %s" % ARCHIS.get(c.get("archi"), {}).get("label", c.get("archi")),
        "Container port   : %s" % c.get("port"),
        "Replicas         : %s" % c.get("replicas"),
    ]
    if size:
        lines.append("Size             : %s (%s) - requests %s CPU / %s, limits %s CPU / %s" % (
            c.get("size"), size["label"], size["requests"]["cpu"], size["requests"]["memory"],
            size["limits"]["cpu"], size["limits"]["memory"]))
    lines += [
        "Protection       : %s - %s" % (c.get("protection"), PROTECTIONS.get(c.get("protection"), "")),
        "Tracing          : %s" % ("enabled (OpenTelemetry)" if c.get("tracing") else "disabled"),
        "Expires          : %s" % (c.get("expires") or "never"),
    ]
    return lines
