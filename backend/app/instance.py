"""Which instance is this? (phase SH-13)

Two copies of the application can run on one machine: production and the
beta instance the testers use (docs/14-beta-instance.md). The scripts name
every resource after CRUCIBLE_INSTANCE; this module turns that same name
into what a person sees in the page's corner, so nobody has to remember
which port is which.

Pure functions, no I/O: the router reads the configuration and calls
``instance_info``; the tests call it with any values they like.
"""

from __future__ import annotations


def instance_label(name: str, override: str = "") -> str:
    """The word shown in the page's corner.

    An explicit override wins ("Production", "UAT"). Otherwise the default
    instance (no name) is "Prod" and a named one is its name with the first
    letter capitalised: "beta" -> "Beta".
    """
    if override:
        return override
    if not name:
        return "Prod"
    return name[:1].upper() + name[1:]


def instance_info(name: str, override: str, port: int, https: bool) -> dict:
    """The answer of GET /api/instance."""
    return {
        "name": name,
        "label": instance_label(name, override),
        "port": port,
        "https": https,
    }
