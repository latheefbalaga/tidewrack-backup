# Narrative — Dialogue Graph Specification

*Tidewrack — Fogline Games · runtime-aligned format · 2026-11-11*

This document describes the flat node-map format consumed by
`DialogueManager` in `scripts/autoload/dialogue_manager.gd`, the story-flag
storage in `GameState`, and the entry points currently used by
`scripts/game.gd`.

## 1. File format

A dialogue file is one JSON object mapping node IDs to node objects.
There is no outer `start` / `nodes` wrapper, and node IDs are not repeated
inside each node. The top-level object key is the node ID.

Each node has these authoring fields:

- `speaker`: required string. Use an empty string for narration.
- `text`: required string containing the line shown for this node.
- Exactly one of:
  - `next`: a node ID string for linear progression, or `null` for a
    terminal node.
  - `choices`: a non-empty array of choice objects for a branching node.
- `set_flag`: optional dictionary of flag-name to value assignments applied
  when the node is entered.

A choice object has:

- `text`: required string displayed as the choice label.
- `next`: required node ID string or `null`. A null destination finishes
  the dialogue immediately after the choice is selected.
- `set_flag`: optional dictionary of flag-name to value assignments applied
  before following the choice destination.

### Complete example

The following is valid JSON in the current flat-map format. Every string
destination exists in this same graph, and both belief choices explicitly
clear the opposite flag.

```json
{
  "start": {
    "speaker": "Keeper's Log",
    "text": "The final page is marked with Edith's initials.",
    "next": "belief_choice"
  },
  "belief_choice": {
    "speaker": "",
    "text": "Do you believe Edith saw something beyond the rocks?",
    "choices": [
      {
        "text": "She was mistaken.",
        "next": "skeptic_end",
        "set_flag": {
          "skeptic": true,
          "believer": false
        }
      },
      {
        "text": "Something was really out there.",
        "next": "believer_end",
        "set_flag": {
          "believer": true,
          "skeptic": false
        }
      }
    ]
  },
  "skeptic_end": {
    "speaker": "",
    "text": "You close the logbook, unconvinced.",
    "next": null
  },
  "believer_end": {
    "speaker": "",
    "text": "You close the logbook, believing Edith.",
    "next": null
  }
}
```

## 2. Runtime behavior

The public entry method is:

```gdscript
func start(path: String, start_id: String = "start") -> bool:
```

- `path` is the dialogue JSON file path (for example,
  `res://data/dialogue/keeper_intro.json`).
- `start_id` is the node ID at which to begin. It defaults to `start`.
- The manager loads the JSON as a dictionary and enters the requested node.
- A missing file, an unreadable file, or a top-level JSON value that is not
  an object causes loading to fail and `start()` returns `false`.
- If the graph loads but `start_id` is absent, the manager reports a missing
  node and finishes the dialogue. The current implementation can still return
  `true` in that case, so callers and validators must ensure entry IDs exist.

The manager emits `dialogue_started`, then `line_shown(speaker, text, choices)`
for each entered node, and `dialogue_finished` when the graph ends. The
dialogue UI listens to those signals; it does not parse the graph itself.

For linear nodes, `advance()` follows `next`. It is ignored while a non-empty
choice list is pending. For branching nodes, `choose(index)` applies the
selected choice's flags and then follows that choice's `next`.

## 3. Terminals and references

A terminal node is a linear node with:

```json
{
  "speaker": "",
  "text": "The scene ends here.",
  "next": null
}
```

When a linear node's `next` is `null`, advancing finishes the dialogue.
A choice whose `next` is `null` also finishes immediately after applying
that choice's `set_flag` assignments.

Authoring rules:

1. Every node ID (top-level key) must be unique.
2. Every node must be an object with string `speaker` and `text`.
3. A node must have exactly one progression form: a `next` field or a
   non-empty `choices` array.
4. Every non-null `next` value must name a node in the same graph.
5. Every choice must include string `text` and a `next` destination
   (string or `null`).
6. Every configured entry point must exist.
7. Every node should be reachable from at least one configured entry, and
   every intended path should reach a terminal.

The manager is deliberately permissive in a few places: it defaults a missing
speaker or text to an empty string, and a missing node/choice `next` is treated
like `null`. These fallbacks are not authoring conventions. Write all required
fields explicitly.

## 4. Story flags

`DialogueManager` supports `set_flag` on either a node or a choice:

- Node-level assignments are applied when the node is entered.
- Choice-level assignments are applied when the player selects that choice,
  before the manager follows its destination.
- Each dictionary key/value pair is passed to
  `GameState.set_flag(name, value)`.
- `GameState` stores values in its `flags` dictionary and persists that
  dictionary in `user://save.json`.

The current project story-flag names are:

- `believer`
- `skeptic`
- `trusted_edith`
- `radioed_tom`

Use Boolean values for these story flags. The current `GameState` API accepts
arbitrary names and Variant values, however; neither `GameState` nor
`DialogueManager` enforces a canonical flag list or Boolean-only values.

**Flags are independent assignments.** Setting `believer` to `true` does not
automatically clear `skeptic`, and setting `skeptic` to `true` does not
automatically clear `believer`. Any mutually exclusive choice must explicitly
write both values. The current keeper-intro choices do this:

- Skeptic: `{"skeptic": true, "believer": false}`
- Believer: `{"believer": true, "skeptic": false}`

The `trusted_edith` choices update only `trusted_edith`; that flag is
independent of the belief choice. The radio choices set `radioed_tom` to
`true`. No ending node changes story flags.

### Ending-state fallback rules

The game router in `scripts/game.gd` applies these rules when it selects an
ending:

- Both `believer` and `skeptic` true: warn, choose Believer, and clear
  `skeptic`.
- Neither true: warn, default to Skeptic, and set
  `believer = false`, `skeptic = true`.
- Missing or non-Boolean `trusted_edith`: warn and default to `false`.
- Missing `radioed_tom`: default to `false` (silent variant). A present
  non-Boolean value is warned about and normalized to `false`.

These are game-router policies, not automatic behavior of `set_flag`.

## 5. Current game entry points and flow

The game passes explicit entry IDs to `DialogueManager.start(path, start_id)`.
The graph-specific entry points currently configured in
`tests/validate_dialogue.py` are:

| File | Entry point(s) | Caller / purpose |
|---|---|---|
| `keeper_intro.json` | `logbook`, `radio`, `door` | Three ground-floor interactables configured in `scripts/game.gd` |
| `lamp_room.json` | `start` | Started after the keeper-intro `door` dialogue finishes |
| `endings.json` | `ending_1_tom`, `ending_1_silent`, `ending_2_tom`, `ending_2_silent`, `ending_3_tom`, `ending_3_silent`, `ending_4_tom`, `ending_4_silent` | Selected by the game router after the lamp-room dialogue finishes |

The current game-flow sequence is:

1. The logbook, radio, and door interactions start their respective
   `keeper_intro.json` entries. The logbook and radio remain independent
   interactions.
2. When the `door` dialogue finishes, `scripts/game.gd` starts
   `lamp_room.json` at `start`.
3. When the lamp-room dialogue finishes, the game reads the story flags and
   starts the appropriate entry in `endings.json`.

New dialogue files not listed above use `start` as the validator's default
configured entry point. Callers may still pass any explicit node ID that
exists in the selected graph.

## 6. Ending graph contract

There are four narrative outcomes and eight entry variants. The
`radioed_tom` flag selects the epilogue variant only; it does not create a
fifth ending.

| Belief | `trusted_edith` | Entry when `radioed_tom` is true | Entry when false | Shared terminal |
|---|---|---|---|---|
| Believer | true | `ending_1_tom` | `ending_1_silent` | `ending_1_leaf` |
| Believer | false | `ending_2_tom` | `ending_2_silent` | `ending_2_leaf` |
| Skeptic | true | `ending_3_tom` | `ending_3_silent` | `ending_3_leaf` |
| Skeptic | false | `ending_4_tom` | `ending_4_silent` | `ending_4_leaf` |

Each `_tom` / `_silent` pair points to the same `ending_N_leaf`, and
each of the four leaves has `"next": null`.

## 7. Validator behavior and limits

Run the engine-free validator from the repository root:

```bash
python3 tests/validate_dialogue.py
```

It scans every `data/dialogue/*.json` file and currently:

- Parses the top-level JSON object and checks the basic linear-versus-choice
  shape (not neither and not both).
- Checks string `next` targets and choice destinations against nodes in the
  same graph.
- Checks that the graph contains at least one terminal.
- Uses graph-specific configured entries for the three current files above;
  other files default to `start`.
- Warns about configured entry IDs that are missing and about nodes
  unreachable from the configured entries.
- Reports flag names found in node-level and choice-level `set_flag`
  dictionaries only. Words in `speaker` or `text` are not treated as flags.

The validator does not yet enforce all authoring rules above. In particular,
it does not verify that `speaker` and `text` are present and strings, that
`set_flag` is a dictionary containing only canonical Boolean flags, or that
every individual entry/path reaches a terminal. A clean static validation
result is not a substitute for running the game in Godot and playtesting every
entry and branch.

## 8. Source of truth

When this document and implementation disagree, the runtime files are
authoritative:

- `scripts/autoload/dialogue_manager.gd`
- `scripts/autoload/game_state.gd`
- `scripts/game.gd`
- `scripts/interactable.gd`
- `tests/validate_dialogue.py`
- `data/dialogue/keeper_intro.json`
- `data/dialogue/lamp_room.json`
- `data/dialogue/endings.json`
