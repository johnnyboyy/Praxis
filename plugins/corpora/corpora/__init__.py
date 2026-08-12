"""Corpora — a pure-composer praxis contributor.

Corpora ships no domains of its own. This package provides the parse layer
(domain-file models, parser, facet-weights loader) and the compose layer
(discovery/precedence merge and the contributor itself).
"""

from __future__ import annotations

from .models import Convention, Domain, Principle
from .parser import parse_domain_file
from .weights import Weights, load_weights

__all__ = [
    "Convention",
    "Principle",
    "Domain",
    "parse_domain_file",
    "Weights",
    "load_weights",
    # Compose layer (import lazily to avoid pulling in the praxis path at
    # package import time; see discovery.py / injector.py).
    "discover_domain_dirs",
    "merge_pool",
    "Corpora",
    "make",
    "shape_ok",
    "render_principles",
    "terse_list",
]


def __getattr__(name):
    # PEP 562 lazy exports: the compose layer touches sys.path for praxis, so
    # only load it on demand.
    if name in ("discover_domain_dirs", "merge_pool"):
        from . import discovery

        return getattr(discovery, name)
    if name in ("Corpora", "make", "shape_ok", "render_principles",
                "terse_list"):
        from . import injector

        return getattr(injector, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
