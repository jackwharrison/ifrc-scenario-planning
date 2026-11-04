"""Loads the shared lists (hazards, sectors, factors, countries) and per-country set-up files.

All lists are plain YAML so they can be changed without touching code.
"""
import functools
import os
import re

import yaml

HERE = os.path.dirname(__file__)


def _load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def slug(country):
    return re.sub(r"[^a-z0-9]+", "-", country.lower()).strip("-")


@functools.lru_cache(maxsize=None)
def hazard_types():
    return _load("hazards.yaml")["hazard_types"]


@functools.lru_cache(maxsize=None)
def sectors():
    return _load("sectors.yaml")["sectors"]


@functools.lru_cache(maxsize=None)
def factors():
    return _load("factors.yaml")["factors"]


def factor_names():
    return [f["name"] for f in factors()]


def factor_context(name):
    for f in factors():
        if f["name"] == name:
            return f["context"]
    return "Environmental and physical"


@functools.lru_cache(maxsize=None)
def countries():
    return _load("countries.yaml")["countries"]


@functools.lru_cache(maxsize=None)
def country_setup(country):
    """Return the set-up for a country, or None if the country is not set up yet."""
    path = os.path.join(HERE, "areas", slug(country) + ".yaml")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def ready_countries():
    return [c["name"] for c in countries() if country_setup(c["name"])]


def area_names(country):
    setup = country_setup(country) or {}
    return [a["name"] for a in setup.get("areas", [])]
