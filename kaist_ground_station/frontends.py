"""Frontend registry: a frontend turns a running StationService into something a person can watch.

A frontend is a callable ``run(service, ui_settings)`` that blocks until the user quits. It may
only use ``service.snapshot()`` and the service's command methods; it must not touch ports,
packets or logs. Modules are imported lazily, so a missing GUI/web dependency only affects
the frontend that needs it. Register new ones (web, curses, ...) below.
"""
from __future__ import annotations

import importlib

FRONTENDS: dict[str, str] = {
    "web": "kaist_ground_station.web.server:run",
    "tk": "kaist_ground_station.ui:run",
}


class FrontendUnavailable(RuntimeError):
    """Raised by a frontend that cannot start here (no display, missing package, ...)."""


def load_frontend(name: str):
    module, _, function = FRONTENDS[name].partition(":")
    return getattr(importlib.import_module(module), function)
