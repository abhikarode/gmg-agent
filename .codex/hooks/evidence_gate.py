#!/usr/bin/python3
"""Global, fail-closed Codex completion-evidence hook."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]")
EXCLUDED_DIRS = {
    ".git", "node_modules", "vendor", "target", "dist", "build", "coverage",
    ".next", ".turbo", ".cache", ".local", "artifacts", "__pycache__",
}
EXCLUDED_PREFIXES = {".codex/evidence/"}
MAX_HASH_BYTES = 10 * 1024 * 1024


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, separators=(",", ":")))


def block(reason: str) -> None:
    emit({
        "continue": False,
        "stopReason": reason,
        "systemMessage": f"Completion evidence rejected. {reason}",
    })


def safe_id(value: str) -> str:
    return SAFE_ID.sub("_", value)


def evidence_dir(cwd: Path) -> Path:
    return cwd / ".codex" / "evidence"


def artifact_path(cwd: Path, session_id: str, subagent: bool, turn_id: str | None) -> Path:
    suffix = f"-subagent-{safe_id(turn_id or 'unknown-turn')}" if subagent else ""
    return evidence_dir(cwd) / f"{safe_id(session_id)}{suffix}.json"


def session_path(cwd: Path, session_id: str) -> Path:
    return evidence_dir(cwd) / f"{safe_id(session_id)}.session.json"


def report_path(cwd: Path, session_id: str) -> Path:
    return evidence_dir(cwd) / f"{safe_id(session_id)}.verification.json"


def manifest_path(cwd: Path) -> Path:
    return cwd / ".codex" / "verification.json"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def project_fingerprint(cwd: Path) -> str:
    digest = hashlib.sha256()
    try:
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=cwd, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=True,
        )
        git_root = Path(root_result.stdout.strip()).resolve()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=git_root, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, check=False,
        ).stdout.strip()
        diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"], cwd=git_root,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20, check=False,
        ).stdout
        digest.update(b"git-v1\0")
        digest.update(head.encode())
        digest.update(diff)
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=git_root,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=False,
        ).stdout.split(b"\0")
        for raw_name in sorted(name for name in untracked if name):
            relative = raw_name.decode(errors="surrogateescape")
            if any(part in EXCLUDED_DIRS for part in Path(relative).parts):
                continue
            path = git_root / relative
            if path.is_file() and path.stat().st_size <= MAX_HASH_BYTES:
                digest.update(relative.encode(errors="surrogateescape"))
                digest.update(bytes.fromhex(hash_file(path)))
        return digest.hexdigest()
    except (OSError, subprocess.SubprocessError):
        pass

    digest.update(b"tree-v1\0")
    for root, directories, files in os.walk(cwd):
        directories[:] = sorted(directory for directory in directories if directory not in EXCLUDED_DIRS)
        root_path = Path(root)
        for filename in sorted(files):
            path = root_path / filename
            relative = path.relative_to(cwd).as_posix()
            if any(relative.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
                continue
            try:
                stat = path.stat()
                if not path.is_file() or stat.st_size > MAX_HASH_BYTES:
                    continue
                digest.update(relative.encode())
                digest.update(str(stat.st_mode & 0o777).encode())
                digest.update(bytes.fromhex(hash_file(path)))
            except OSError:
                continue
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def initial_artifact(session_id: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "gate": "PENDING",
        "evidence_types": [],
        "execution_refs": [],
        "requirements": [],
        "requires_multipersona": False,
        "notes": "Populate with fresh, observed evidence after verification.",
    }


def validate_artifact(data: Any, session_id: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["completion artifact must be a JSON object"]
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("session_id") != session_id:
        errors.append("completion artifact session_id does not match")
    if data.get("gate") != "PASS":
        errors.append("completion artifact gate must be PASS")
    types = data.get("evidence_types")
    if not isinstance(types, list) or "EXECUTION" not in types:
        errors.append("evidence_types must contain EXECUTION")
    if data.get("requires_multipersona") is True and (
        not isinstance(types, list) or "MULTIPERSONA" not in types
    ):
        errors.append("MULTIPERSONA evidence is required")
    refs = data.get("execution_refs")
    known: set[str] = set()
    if not isinstance(refs, list) or not refs:
        errors.append("execution_refs must be non-empty")
    else:
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"execution_refs[{index}] must be an object")
                continue
            ref_id = ref.get("id")
            if not isinstance(ref_id, str) or not ref_id.strip() or ref_id in known:
                errors.append(f"execution_refs[{index}].id must be unique and non-empty")
            else:
                known.add(ref_id)
            if ref.get("kind") not in {"command", "test", "observation"}:
                errors.append(f"execution_refs[{index}].kind is invalid")
            if ref.get("result") != "PASS":
                errors.append(f"execution_refs[{index}].result must be PASS")
            if ref.get("kind") in {"command", "test"} and ref.get("exit_code") != 0:
                errors.append(f"execution_refs[{index}].exit_code must be 0")
            if not isinstance(ref.get("summary"), str) or not ref["summary"].strip():
                errors.append(f"execution_refs[{index}].summary is required")
    requirements = data.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        errors.append("requirements must be non-empty")
    else:
        requirement_ids: set[str] = set()
        for index, requirement in enumerate(requirements):
            if not isinstance(requirement, dict):
                errors.append(f"requirements[{index}] must be an object")
                continue
            requirement_id = requirement.get("id")
            if not isinstance(requirement_id, str) or not requirement_id.strip() or requirement_id in requirement_ids:
                errors.append(f"requirements[{index}].id must be unique and non-empty")
            else:
                requirement_ids.add(requirement_id)
            if requirement.get("status") != "PASS":
                errors.append(f"requirements[{index}].status must be PASS")
            linked = requirement.get("execution_refs")
            if not isinstance(linked, list) or not linked:
                errors.append(f"requirements[{index}].execution_refs must be non-empty")
            elif any(ref not in known for ref in linked):
                errors.append(f"requirements[{index}] links unknown evidence")
    return errors


def validate_report(report: Any, manifest: Any, session_id: str, fingerprint: str, manifest_hash: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["verification report must be a JSON object"]
    if report.get("schema_version") != 1:
        errors.append("verification report schema_version must be 1")
    if report.get("session_id") != session_id:
        errors.append("verification report belongs to another session")
    if report.get("project_fingerprint") != fingerprint:
        errors.append("project changed after verification; rerun codex-verify")
    if report.get("manifest_sha256") != manifest_hash:
        errors.append("verification manifest changed; rerun codex-verify")
    checks = report.get("checks")
    report_checks = {
        check.get("id"): check for check in checks or [] if isinstance(check, dict)
    }
    required = [
        check for check in manifest.get("checks", [])
        if isinstance(check, dict) and check.get("required", True)
    ]
    for check in required:
        result = report_checks.get(check.get("id"))
        if not result:
            errors.append(f"required check {check.get('id')} was not executed")
        elif result.get("exit_code") != 0 or result.get("result") != "PASS":
            errors.append(f"required check {check.get('id')} did not pass")
        elif not isinstance(result.get("log_sha256"), str):
            errors.append(f"required check {check.get('id')} has no log checksum")
    return errors


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as exc:
        block(f"Hook input is not valid JSON: {exc}")
        return 0
    cwd = Path(event.get("cwd") or ".").resolve()
    session_id = event.get("session_id")
    event_name = event.get("hook_event_name")
    if not isinstance(session_id, str) or not session_id:
        block("Hook input has no session_id")
        return 0
    evidence_dir(cwd).mkdir(parents=True, exist_ok=True)
    artifact = artifact_path(
        cwd, session_id, event_name == "SubagentStop",
        event.get("turn_id") if isinstance(event.get("turn_id"), str) else None,
    )
    if event_name == "SessionStart":
        if not artifact.exists():
            artifact.write_text(json.dumps(initial_artifact(session_id), indent=2) + "\n", encoding="utf-8")
        manifest = manifest_path(cwd)
        state = {
            "schema_version": 1,
            "session_id": session_id,
            "baseline_fingerprint": project_fingerprint(cwd),
            "manifest_sha256": hash_file(manifest) if manifest.is_file() else None,
        }
        session_path(cwd, session_id).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        emit({
            "continue": True,
            "systemMessage": (
                "Global completion discipline is active. Source changes require a current "
                "`~/.codex/bin/codex-verify` report and linked completion evidence."
            ),
        })
        return 0
    if event_name not in {"Stop", "SubagentStop"}:
        return 0
    current_fingerprint = project_fingerprint(cwd)
    state_file = session_path(cwd, session_id)
    state = load_json(state_file) if state_file.is_file() else {}
    unchanged = state.get("baseline_fingerprint") == current_fingerprint
    if unchanged:
        emit({"continue": True, "systemMessage": "Project source state is unchanged; no execution gate is required."})
        return 0
    manifest_file = manifest_path(cwd)
    if not manifest_file.is_file():
        block("Source changed but .codex/verification.json is missing. Run ~/.codex/bin/codex-discipline-init.")
        return 0
    try:
        manifest = load_json(manifest_file)
    except (json.JSONDecodeError, OSError) as exc:
        block(f"Cannot read verification manifest: {exc}")
        return 0
    if not artifact.is_file():
        block(f"Missing completion artifact: {artifact}")
        return 0
    try:
        artifact_data = load_json(artifact)
        artifact_errors = validate_artifact(artifact_data, session_id)
    except (json.JSONDecodeError, OSError) as exc:
        block(f"Cannot read completion artifact: {exc}")
        return 0
    report_file = report_path(cwd, session_id)
    if not report_file.is_file():
        block(f"Missing verification report. Run ~/.codex/bin/codex-verify --session-id {session_id}")
        return 0
    try:
        report = load_json(report_file)
        report_errors = validate_report(
            report, manifest, session_id, current_fingerprint, hash_file(manifest_file),
        )
    except (json.JSONDecodeError, OSError) as exc:
        block(f"Cannot read verification report: {exc}")
        return 0
    errors = artifact_errors + report_errors
    if errors:
        block("; ".join(errors))
        return 0
    emit({
        "continue": True,
        "systemMessage": (
            "Fresh verification and linked completion evidence match the active session, "
            "manifest, and current project state."
        ),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
