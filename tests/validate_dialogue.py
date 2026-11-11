#!/usr/bin/env python3
"""Validate Tidewrack dialogue graphs without needing the Godot engine.

Checks, for every data/dialogue/*.json file:
  - it parses as a JSON object of node_id -> node
  - each node is either a linear node ("next": id|null) or a choice node
    ("choices": [{text, next, set_flag?}]) — not neither, not both
  - every referenced target id exists
  - at least one terminal (next == null) is reachable from an entry point
  - reports orphan nodes (unreachable from any known entry) as warnings

Exit code 0 = all valid, 1 = at least one error.

Usage:  python3 tests/validate_dialogue.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Exact entry points used by each dialogue file in the current game flow.
# Endings are entered directly by scripts/game.gd using one of the eight
# belief/trust + radio variants; they do not start at "start".
ENTRY_POINTS_BY_FILE = {
    "keeper_intro.json": {"logbook", "radio", "door"},
    "lamp_room.json": {"start"},
    "endings.json": {
        "ending_1_tom", "ending_1_silent",
        "ending_2_tom", "ending_2_silent",
        "ending_3_tom", "ending_3_silent",
        "ending_4_tom", "ending_4_silent",
    },
}
# New dialogue files follow DialogueManager.start(path)'s default entry.
DEFAULT_ENTRY_POINTS = {"start"}

ROOT = Path(__file__).resolve().parent.parent
DIALOGUE_DIR = ROOT / "data" / "dialogue"


def reachable(graph: dict, entries: set[str]) -> set[str]:
    seen: set[str] = set()
    stack = [e for e in entries if e in graph]
    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)
        node = graph[nid]
        targets: list[str] = []
        if isinstance(node.get("choices"), list):
            targets += [c.get("next") for c in node["choices"]]
        if "next" in node:
            targets.append(node.get("next"))
        for t in targets:
            if isinstance(t, str) and t in graph:
                stack.append(t)
    return seen



def collect_set_flags(graph: dict) -> set[str]:
    """Collect flag names only from set_flag dictionaries on nodes and choices.

    Dialogue prose is intentionally ignored; mentioning a flag name in
    speaker/text content does not mean the graph sets that flag.
    """
    flags: set[str] = set()
    for node in graph.values():
        if not isinstance(node, dict):
            continue

        node_flags = node.get("set_flag")
        if isinstance(node_flags, dict):
            flags.update(str(name) for name in node_flags)

        choices = node.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                choice_flags = choice.get("set_flag")
                if isinstance(choice_flags, dict):
                    flags.update(str(name) for name in choice_flags)

    return flags


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        graph = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON — {exc}"], warnings

    if not isinstance(graph, dict):
        return [f"{path.name}: top level must be an object of node_id -> node"], warnings

    has_terminal = False
    for nid, node in graph.items():
        if not isinstance(node, dict):
            errors.append(f"{path.name}:{nid}: node must be an object")
            continue

        has_choices = isinstance(node.get("choices"), list) and len(node["choices"]) > 0
        has_next = "next" in node

        if not has_choices and not has_next:
            errors.append(f"{path.name}:{nid}: node has neither 'next' nor 'choices'")
        if has_choices and has_next:
            errors.append(f"{path.name}:{nid}: node has both 'next' and 'choices' (ambiguous)")

        if has_next and node.get("next") is None:
            has_terminal = True

        if has_next and isinstance(node.get("next"), str) and node["next"] not in graph:
            errors.append(f"{path.name}:{nid}: 'next' points to missing node '{node['next']}'")

        if has_choices:
            for i, choice in enumerate(node["choices"]):
                if not isinstance(choice, dict) or "text" not in choice:
                    errors.append(f"{path.name}:{nid}: choice #{i} needs a 'text' field")
                    continue
                target = choice.get("next")
                if target is not None and (not isinstance(target, str) or target not in graph):
                    errors.append(f"{path.name}:{nid}: choice #{i} 'next' -> missing node '{target}'")
                if target is None:
                    has_terminal = True

    if not has_terminal:
        errors.append(f"{path.name}: no terminal node (a node with next == null) — the graph never ends")

    configured_entries = ENTRY_POINTS_BY_FILE.get(path.name, DEFAULT_ENTRY_POINTS)
    entries = configured_entries & set(graph.keys())

    missing_entries = configured_entries - set(graph.keys())
    if missing_entries:
        warnings.append(
            f"{path.name}: missing configured entry point(s) {sorted(missing_entries)}"
        )

    if not entries:
        warnings.append(
            f"{path.name}: no configured entry point present "
            f"({sorted(configured_entries)})"
        )
    else:
        seen = reachable(graph, entries)
        for orphan in sorted(set(graph) - seen):
            warnings.append(
                f"{path.name}:{orphan}: unreachable from entry points {sorted(entries)}"
            )

    return errors, warnings


def main() -> int:
    files = sorted(DIALOGUE_DIR.glob("*.json"))
    if not files:
        print(f"No dialogue files found in {DIALOGUE_DIR}")
        return 1

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for path in files:
        errs, warns = validate_file(path)
        all_errors += errs
        all_warnings += warns

        try:
            graph = json.loads(path.read_text())
        except json.JSONDecodeError:
            graph = {}

        node_count = len(graph) if isinstance(graph, dict) else 0
        flags = collect_set_flags(graph) if isinstance(graph, dict) else set()
        flag_summary = ", ".join(sorted(flags)) if flags else "none"
        status = "OK" if not errs else "FAIL"
        print(
            f"[{status}] {path.relative_to(ROOT)}  "
            f"({node_count} nodes) | flags: {flag_summary}"
        )

    for w in all_warnings:
        print(f"  warning: {w}")
    for e in all_errors:
        print(f"  ERROR:   {e}")

    print()
    if all_errors:
        print(f"✗ {len(all_errors)} error(s), {len(all_warnings)} warning(s)")
        return 1
    print(f"✓ all dialogue graphs valid ({len(all_warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# --- Public Demo: journal graphs -------------------------------------------
# The journal system (scripts/journal.gd) reads discovered-log entries from the
# same JSON-graph format, so they validate through the checker above. Journal
# graphs live under data/dialogue/ with an "entry_*" id and are held to the same
# rules (targets resolve, a terminal exists). This hook is a placeholder until
# the journal content lands for the public demo.
JOURNAL_ENTRY_PREFIX = "entry_"


def is_journal_graph(graph: dict) -> bool:
	return any(str(k).startswith(JOURNAL_ENTRY_PREFIX) for k in graph)
