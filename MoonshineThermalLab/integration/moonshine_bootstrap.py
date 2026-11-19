"""Load the verified upstream package without pip/editable-install metadata.

Candidate for integration/moonshine_bootstrap.py. Call before importing any
Moonshine configuration, provider or app module. This only registers Python
imports; it never constructs a provider or invokes a model.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from threading import RLock
from types import ModuleType

from .source_integrity import source_identity

_LOCK = RLock()


def _check_registered_modules(source: Path, identity: dict) -> None:
    declared = identity["tracked_files_sha256"]
    for name, module in list(sys.modules.items()):
        if name != "moonshine" and not name.startswith("moonshine."):
            continue
        if not isinstance(module, ModuleType):
            raise RuntimeError("Conflicting Moonshine module registration: " + name)
        location = module.__dict__.get("__file__")
        spec = module.__dict__.get("__spec__")
        if not location or not spec or not spec.origin:
            raise RuntimeError("Moonshine module has no verifiable file origin: " + name)
        path = Path(location).resolve()
        try:
            relative = path.relative_to(source).as_posix()
        except ValueError as exc:
            raise RuntimeError("Moonshine is already loaded from a different source: " + name) from exc
        if relative not in declared or Path(spec.origin).resolve() != path:
            raise RuntimeError("Moonshine module is not from the pinned source files: " + name)
        if name == "moonshine" and path != source / "__init__.py":
            raise RuntimeError("Moonshine root package has the wrong file origin.")
        package_paths = module.__dict__.get("__path__")
        if package_paths is not None:
            expected = path.parent
            if [Path(item).resolve() for item in package_paths] != [expected]:
                raise RuntimeError("Moonshine package search path is not its pinned directory: " + name)


def bootstrap_moonshine(source: Path | str, manifest_path: Path | str) -> ModuleType:
    """Verify 163 source files, register/reuse their package, reject collisions.

    Call during single-threaded application startup, before building the app.
    Existing foreign Moonshine registrations are never silently replaced.
    """
    with _LOCK:
        identity = source_identity(source, manifest_path)
        source = Path(source).resolve()
        if "moonshine" in sys.modules:
            _check_registered_modules(source, identity)
            return sys.modules["moonshine"]
        if any(name.startswith("moonshine.") for name in sys.modules):
            raise RuntimeError("Moonshine child modules exist without a registered root package.")
        spec = importlib.util.spec_from_file_location(
            "moonshine", source / "__init__.py", submodule_search_locations=[str(source)]
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Cannot construct the pinned Moonshine package spec.")
        module = importlib.util.module_from_spec(spec)
        sys.modules["moonshine"] = module
        try:
            spec.loader.exec_module(module)
            _check_registered_modules(source, identity)
        except BaseException:
            # No Moonshine names existed before registration. Only remove names
            # whose recorded origins are inside this source, never other imports.
            for name, loaded in list(sys.modules.items()):
                if name != "moonshine" and not name.startswith("moonshine."):
                    continue
                location = getattr(loaded, "__dict__", {}).get("__file__")
                if location and Path(location).resolve().is_relative_to(source):
                    sys.modules.pop(name, None)
            raise
        return module
