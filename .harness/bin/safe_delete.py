#!/usr/bin/env python3
"""Reversible workspace deletion by quarantine; permanent removal is absent."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


CONTROL_PLANE = {
    ".git",
    ".harness",
    ".claude",
    ".claude-plugin",
    ".codex",
    ".codex-plugin",
    ".gemini",
    ".agents",
    "hooks",
    "skills",
    "AGENTS.md",
    "ORCHESTRATION.md",
    "claude.md",
    "gemini.md",
    "GEMINI.md",
}

# Membership checks against CONTROL_PLANE must be case-insensitive: the repo's
# real file is CLAUDE.md, but CONTROL_PLANE only lists the lowercase spelling,
# and case-sensitive membership would let "CLAUDE.md" (and other differently
# cased control-plane entries) slip past both the quarantine guard and restore.
_CONTROL_PLANE_LOWER = {name.lower() for name in CONTROL_PLANE}


class SafetyError(Exception):
    pass


def _root(value: Optional[str]) -> Path:
    root = Path(value).expanduser() if value else Path(__file__).resolve().parents[2]
    return root.absolute().resolve()


def _validate(root: Path, raw: str) -> Tuple[Path, Path]:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    absolute = candidate.absolute()
    try:
        relative = absolute.relative_to(root)
    except ValueError as exc:
        raise SafetyError("outside workspace: {}".format(raw)) from exc
    if relative == Path("."):
        raise SafetyError("refusing workspace root")
    if not absolute.exists() and not absolute.is_symlink():
        raise SafetyError("path does not exist: {}".format(raw))
    # Refuse symlinks (or symlinked parents) that escape the workspace.
    try:
        absolute.resolve().relative_to(root)
    except ValueError as exc:
        raise SafetyError("path resolves outside workspace: {}".format(raw)) from exc
    if relative.parts and relative.parts[0].lower() in _CONTROL_PLANE_LOWER:
        raise SafetyError("control-plane path is protected: {}".format(relative))
    return absolute, relative


def _write_manifest(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _agent() -> str:
    return (
        os.environ.get("CLAUDE_HARNESS_AGENT_ID")
        or os.environ.get("HARNESS_AGENT_ID")
        or os.environ.get("CODEX_THREAD_ID")
        or "codex"
    )


def _log_event(root: Path, event: str, **fields) -> None:
    try:
        path = root / ".harness" / "logs" / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "agent": _agent(),
        }
        record.update(fields)
        with path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            fcntl.flock(handle, fcntl.LOCK_UN)
    except Exception:
        # Audit logging must not corrupt or strand a completed reversible move.
        pass


def quarantine(root: Path, raw_paths: Iterable[str], reason: str) -> dict:
    validated = [_validate(root, raw) for raw in raw_paths]
    if not validated:
        raise SafetyError("at least one path is required")
    relatives = [relative for _, relative in validated]
    if len(set(relatives)) != len(relatives):
        raise SafetyError("duplicate path")
    for left in relatives:
        for right in relatives:
            if left != right and left in right.parents:
                raise SafetyError("overlapping paths are not allowed: {} and {}".format(left, right))

    entry_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    entry = root / ".harness" / "trash" / entry_id
    payload = entry / "payload"
    payload.mkdir(parents=True, exist_ok=False)
    moved: List[dict] = []
    try:
        for source, relative in validated:
            destination = payload / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append({"original": str(relative), "stored": str(Path("payload") / relative)})
        manifest = {
            "id": entry_id,
            "quarantined_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent": _agent(),
            "reason": reason,
            "status": "quarantined",
            "items": moved,
        }
        _write_manifest(entry / "manifest.json", manifest)
        _log_event(
            root,
            "safe_delete_quarantined",
            quarantine_id=entry_id,
            reason=reason,
            paths=[item["original"] for item in moved],
        )
        return manifest
    except Exception:
        # Best-effort rollback means a failed quarantine cannot silently lose
        # sources after only a subset was moved.
        for item in reversed(moved):
            stored = entry / item["stored"]
            original = root / item["original"]
            if stored.exists() or stored.is_symlink():
                original.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(stored), str(original))
        raise


def list_entries(root: Path) -> list:
    trash = root / ".harness" / "trash"
    result = []
    if not trash.exists():
        return result
    for manifest_path in sorted(trash.glob("*/manifest.json")):
        try:
            result.append(json.loads(manifest_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            result.append({"id": manifest_path.parent.name, "status": "invalid-manifest"})
    return result


def restore(root: Path, entry_id: str) -> dict:
    if entry_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", entry_id):
        raise SafetyError("invalid quarantine id")
    entry = root / ".harness" / "trash" / entry_id
    manifest_path = entry / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError("unknown or invalid quarantine entry: {}".format(entry_id)) from exc
    if manifest.get("status") != "quarantined":
        raise SafetyError("entry is not restorable: {}".format(manifest.get("status")))

    trash_root = (root / ".harness" / "trash").resolve()
    entry_resolved = entry.resolve()
    payload_root = (entry / "payload").resolve()
    try:
        entry_resolved.relative_to(trash_root)
        payload_root.relative_to(entry_resolved)
    except ValueError as exc:
        raise SafetyError("quarantine entry or payload escapes the trash directory") from exc
    if entry_resolved.parent != trash_root or entry.is_symlink():
        raise SafetyError("quarantine entry must be a direct, non-symlink child of trash")

    planned = []
    for item in manifest.get("items", []):
        raw_stored = item.get("stored")
        if not isinstance(raw_stored, str):
            raise SafetyError("invalid stored path in manifest")
        stored = Path(raw_stored)
        if stored.is_absolute() or ".." in stored.parts or len(stored.parts) < 2:
            raise SafetyError("unsafe stored path in manifest: {}".format(raw_stored))
        if stored.parts[0] != "payload":
            raise SafetyError("stored path must be below payload/: {}".format(raw_stored))
        source = entry / stored
        try:
            source.resolve().relative_to(payload_root)
        except ValueError as exc:
            raise SafetyError(
                "stored path escapes quarantine payload: {}".format(raw_stored)
            ) from exc
        destination, relative = _destination_for_restore(root, item["original"])
        if destination.exists() or destination.is_symlink():
            raise SafetyError("restore would overwrite existing path: {}".format(relative))
        if not source.exists() and not source.is_symlink():
            raise SafetyError("quarantined payload is missing: {}".format(item["stored"]))
        planned.append((source, destination))

    restored = []
    try:
        for source, destination in planned:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            restored.append((source, destination))
    except Exception:
        for source, destination in reversed(restored):
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(source))
        raise

    manifest["status"] = "restored"
    manifest["restored_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["restored_by"] = _agent()
    _write_manifest(manifest_path, manifest)
    _log_event(
        root,
        "safe_delete_restored",
        quarantine_id=entry_id,
        paths=[item["original"] for item in manifest.get("items", [])],
    )
    return manifest


def _destination_for_restore(root: Path, raw_relative: str) -> Tuple[Path, Path]:
    relative = Path(raw_relative)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise SafetyError("unsafe original path in manifest")
    if relative.parts[0].lower() in _CONTROL_PLANE_LOWER:
        raise SafetyError("manifest targets protected control-plane path")
    destination = (root / relative).absolute()
    try:
        destination.relative_to(root)
        destination.parent.resolve().relative_to(root)
    except ValueError as exc:
        raise SafetyError("manifest targets outside workspace or through an escaping symlink") from exc
    return destination, relative


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--root", help="workspace root (primarily for isolated testing)")
    commands = result.add_subparsers(dest="action", required=True)
    quarantine_parser = commands.add_parser("quarantine", help="move paths into reversible quarantine")
    quarantine_parser.add_argument("paths", nargs="+")
    quarantine_parser.add_argument(
        "--reason", default="reversible cleanup (no reason supplied)", help="audit reason stored with the entry"
    )
    commands.add_parser("list", help="list quarantine entries as JSON")
    restore_parser = commands.add_parser("restore", help="restore an entry without overwriting")
    restore_parser.add_argument("id")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    root = _root(args.root)
    try:
        if args.action == "quarantine":
            output = quarantine(root, args.paths, args.reason)
        elif args.action == "list":
            output = list_entries(root)
        else:
            output = restore(root, args.id)
    except SafetyError as exc:
        print("SAFE DELETE REFUSED: {}".format(exc), file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
