"""Pinned upstream source identity for a real clone or a Git-free vendor copy.

Candidate only until deployed into integration/. This module never writes files
or reads credentials. Bytecode caches for listed Python sources are tolerated,
but are not part of the source identity and must be excluded from distribution.
"""
from __future__ import annotations

import hashlib
from importlib.util import source_from_cache
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

PINNED_REPOSITORY = "https://github.com/DeepMathLLM/Moonshine"
PINNED_COMMIT = "bb0e4aa025fdcc5297fff1025ab4876f120ed615"
PINNED_FILE_COUNT = 163
PINNED_MANIFEST_CANONICAL_SHA256 = "5f5314b9e29d1cde2ce777db00d5681b6b42eac3ce2bf259ea2e17401be8c925"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_redirect(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate manifest property: " + key)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Non-finite manifest number: " + value)


def _load_manifest(path: Path) -> dict:
    if _is_redirect(path) or not path.is_file():
        raise ValueError("Pinned source manifest must be an ordinary file.")
    manifest = json.loads(path.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=_unique_pairs, parse_constant=_invalid_constant)
    if not isinstance(manifest, dict) or set(manifest) != {"repository", "commit", "tracked_files_sha256"}:
        raise ValueError("Unexpected source manifest structure.")
    if manifest["repository"] != PINNED_REPOSITORY or manifest["commit"] != PINNED_COMMIT:
        raise ValueError("Source manifest repository or commit differs from the pin.")
    hashes = manifest["tracked_files_sha256"]
    if not isinstance(hashes, dict) or len(hashes) != PINNED_FILE_COUNT:
        raise ValueError("Source manifest must contain exactly %d files." % PINNED_FILE_COUNT)
    casefolded = set()
    for name, expected in hashes.items():
        if not isinstance(name, str) or not name or any(ord(c) < 32 for c in name) or ":" in name or "\\" in name:
            raise ValueError("Invalid source manifest relative path.")
        relative = PurePosixPath(name)
        if (relative.is_absolute() or name != relative.as_posix() or
                any(part in {".", ".."} or part.casefold() == ".git" for part in relative.parts)):
            raise ValueError("Unsafe source manifest relative path: " + name)
        if name.casefold() in casefolded:
            raise ValueError("Case-colliding source manifest path: " + name)
        casefolded.add(name.casefold())
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid file SHA256 in source manifest: " + name)
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != PINNED_MANIFEST_CANONICAL_SHA256:
        raise ValueError("Pinned source manifest canonical SHA256 mismatch.")
    return manifest


def _git_output(source: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(source), *arguments], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding="utf-8", errors="strict", timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Unable to verify the source's own Git repository.") from exc
    return result.stdout


def _is_allowed_cache(path: Path, source: Path, declared: dict) -> bool:
    if path.parent.name != "__pycache__" or path.suffix != ".pyc":
        return False
    try:
        python_source = Path(source_from_cache(str(path)))
        name = python_source.relative_to(source).as_posix()
    except ValueError:
        return False
    return name in declared and name.endswith(".py")


def source_identity(source: Path | str, manifest_path: Path | str) -> dict:
    """Return the same verified 163-file identity in clone and vendor modes.

    Git-free vendor mode never invokes Git, even inside an unrelated parent
    repository. A .git marker that exists but is invalid never falls back.
    """
    original_source = Path(source).absolute()
    if _is_redirect(original_source) or not original_source.is_dir():
        raise ValueError("Source must be an ordinary directory, not a link/junction.")
    source = original_source.resolve()
    manifest = _load_manifest(Path(manifest_path))
    declared = manifest["tracked_files_sha256"]
    marker = source / ".git"
    has_own_git = marker.exists() or marker.is_symlink()
    if has_own_git:
        if _is_redirect(marker):
            raise ValueError("Source .git marker cannot be a link/junction.")
        top = Path(_git_output(source, "rev-parse", "--show-toplevel").strip()).resolve()
        if top != source:
            raise ValueError("Git top-level is not the source directory; refusing parent repository identity.")
        head = _git_output(source, "rev-parse", "HEAD").strip()
        if head != PINNED_COMMIT:
            raise ValueError("Source Git HEAD differs from the pinned commit.")
        _git_output(source, "diff", "--exit-code", "HEAD", "--")
        tracked = {name for name in _git_output(source, "ls-files", "-z").split("\0") if name}
        if tracked != set(declared):
            raise ValueError("Git tracked file set differs from the pinned source manifest.")

    found = {}
    for directory, directory_names, filenames in os.walk(source, followlinks=False):
        parent = Path(directory)
        for name in list(directory_names):
            child = parent / name
            if parent == source and name == ".git" and has_own_git:
                directory_names.remove(name)
                continue
            if _is_redirect(child):
                raise ValueError("Linked directory in pinned source: " + str(child))
            child.resolve().relative_to(source)
        for name in filenames:
            child = parent / name
            if parent == source and name == ".git" and has_own_git:
                continue
            if _is_redirect(child) or not child.is_file():
                raise ValueError("Linked or nonregular file in pinned source: " + str(child))
            child.resolve().relative_to(source)
            relative = child.relative_to(source).as_posix()
            if relative not in declared:
                if _is_allowed_cache(child, source, declared):
                    continue
                raise ValueError("Unexpected file in pinned source: " + relative)
            found[relative] = _sha(child)
    missing = sorted(set(declared) - set(found))
    mismatched = sorted(name for name, actual in found.items() if declared[name] != actual)
    if missing or mismatched:
        raise ValueError("Pinned source verification failed; missing=%r; mismatched=%r" % (missing, mismatched))
    return {"repository": PINNED_REPOSITORY, "commit": PINNED_COMMIT,
            "tracked_files_sha256": dict(sorted(found.items()))}
