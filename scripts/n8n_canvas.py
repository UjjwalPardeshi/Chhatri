"""Where everything sits on the n8n canvas of a Chhatri workflow (looks only, no behaviour).

Left to right on one row: webhook -> secret check -> step 1 .. step n -> Completed (200). The reject
branch sits below and to the right of the secret check, so n8n draws its edge forward (down from the
check's `false` output) instead of a loop back to the left. Sticky notes frame their nodes, text on top,
nodes below the text:

    +----------------------------- title: what starts it, n8n never decides ---------------------------+
    +-- security (red) ------------+  +-- checklist (green): what each step does, simulated times -------+
    |  webhook -> secret check     |  |  step 1 -> step 2 -> ... -> Completed (200)                     |
    |                 |            |  +-------------------------------------------------------------------+
    |                 `-> reject + |  +-- if a step fails (gold) ----------------------------------------+
    +------------------------------+  +-------------------------------------------------------------------+

The geometry is n8n 2.41.3's, read from its editor bundle and measured on the canvas: nodes are 96 x 96,
positions snap to a 16 px grid (so every position here is a multiple of 16 and renders exactly), a name
sits centred under its node in a 192 px box (two lines at most) with the notes as one 192 px line under
it, an output handle ends 104 px right of the node's x and an input handle starts 8 px left of it, and an
output with no connection shows a "+" stub 104 to 174 px right of the node's x. Sticky text heights are a
conservative estimate (14 px body, 24 px `##`, 16 px `###`, 8/12 px padding, overflow hidden). The tests
check that nothing overlaps, every node and stub sits inside its frame below the frame's text, the
reject edge is drawn forward, and zoom to fit at 1280 x 720 stays readable.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

GRID: Final = 16  # n8n snaps node and sticky positions to it
SIZE_STEP: Final = 16  # sticky sizes, so frame edges stay on the grid
NODE_SIZE: Final = 96  # n8n's default node size
PITCH: Final = 208  # step to step: a step's 192 px notes line + a 16 px gap
SHORT_PITCH: Final = 192  # webhook to check, last step to Completed (200): no notes line between them
LABEL_OVERHANG: Final = 48  # a step's name and notes box is 192 px wide, centred on the node
LABEL_MAX: Final = 2 * NODE_SIZE  # n8n's name box: min-width twice the node width, two lines at most
LABEL_CHAR_W: Final = 8.5  # px per character of a node name (n8n renders about 7.8)
LABEL_PAD: Final = 10
LABEL_TOP: Final = 7  # node bottom to its name (measured)
LABEL_LINE: Final = 20  # one line of a node's name (measured)
LABEL_DEPTH: Final = 70  # two lines of name + one line of notes under a step node
PLAIN_LABEL_DEPTH: Final = 50  # two lines of name, no notes
FRAME_PAD: Final = 10  # frame edge to the nearest node zone
STICKY_GAP: Final = 16  # between two sticky notes
TEXT_GAP: Final = 10  # frame text to the nodes below it
REJECT_SHIFT: Final = 96  # Reject sits this far right of the check: its edge is drawn forward
REJECT_GAP: Final = 16  # the check's name to the Reject node below it
MIN_STEP_COLUMNS: Final = 4  # every canvas is as wide as payout's, so all three zoom alike

# n8n 2.41.3 draws an edge as a loop back to the left when sourceX - 20 > targetX (its
# `isRightOfSourceHandle`); otherwise a curve. Edge ends measured on the canvas: sourceX = x + 104,
# targetX = x - 8 for nodes on the grid.
BACKWARD_SLACK: Final = 20
HANDLE_OUT: Final = 104
HANDLE_IN: Final = -8
FALSE_OUT_Y: Final = 64  # the IF node's `false` output handle: y + 64 (its `true` one is at y + 32)
INPUT_Y: Final = 48  # a node's input handle: y + 48
CURVATURE: Final = 0.25  # Vue Flow's default bezier curvature, which n8n keeps
STUB_X: Final = 104  # the "+" stub of an output without a connection: x + 104 .. x + 174
STUB_W: Final = 70
STUB_Y: Final = 35  # y + 35 .. y + 61
STUB_H: Final = 26

# Zoom to fit in a 1280 x 720 window (n8n 2.41.3): the canvas area is 1238 x 620 and fit view pads the
# bounds by 20 %, so zoom = min(FIT_W / width, FIT_H / height) of the rendered bounds. Measured: 0.6499
# for 1528 x 794, 0.6754 for 1528 x 714 and 0.6667 for 1546 x 774.
FIT_W: Final = 1031.6
FIT_H: Final = 516.0

# Sticky colours of n8n 2.x: 1 yellow, 2 gold, 3 red, 4 green, 5 blue, 6 purple, 7 grey.
COLOR_TITLE: Final = 5
COLOR_SECURITY: Final = 3
COLOR_CHECKLIST: Final = 4
COLOR_FAILURE: Final = 2

# Text metrics (conservative: wider and taller than n8n renders them).
PAD_TOP: Final = 8
PAD_X: Final = 12
BORDER: Final = 2
BLOCK_GAP: Final = 8
LIST_INDENT: Final = 20
LIST_ITEM_GAP: Final = 4
SAFETY: Final = 10  # extra height below the last line
METRICS: Final = {"h2": (12.8, 33.0), "h3": (8.6, 22.0), "p": (7.0, 19.0)}  # (px per char, line height)
MARKUP = re.compile(r"[*`]")


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    def overlaps(self, other: Rect) -> bool:
        return (
            self.x < other.right and other.x < self.right and self.y < other.bottom and other.y < self.bottom
        )

    def contains(self, other: Rect) -> bool:
        return (
            self.x <= other.x
            and other.right <= self.right
            and self.y <= other.y
            and other.bottom <= self.bottom
        )


@dataclass(frozen=True, slots=True)
class Sticky:
    key: str
    color: int
    rect: Rect
    content: str


@dataclass(frozen=True, slots=True)
class Markdown:
    """The four sticky texts of one workflow."""

    title: str
    security: str
    checklist: str
    failure: str


@dataclass(frozen=True, slots=True)
class RowNames:
    """Names of the nodes without notes; their width decides how close they may sit."""

    webhook: str
    check: str
    done: str
    reject: str


@dataclass(frozen=True, slots=True)
class Layout:
    webhook: tuple[int, int]
    check: tuple[int, int]
    steps: tuple[tuple[int, int], ...]
    done: tuple[int, int]
    reject: tuple[int, int]
    stickies: tuple[Sticky, ...]


def label_width(name: str) -> int:
    """Conservative width of a node's name under it (one line, or the full box when it wraps)."""
    return min(LABEL_MAX, math.ceil(len(name) * LABEL_CHAR_W + LABEL_PAD))


def node_zone(position: Sequence[int]) -> Rect:
    """A step node with the name and the notes line n8n draws under it (192 px wide)."""
    x, y = position
    return Rect(x - LABEL_OVERHANG, y, NODE_SIZE + 2 * LABEL_OVERHANG, NODE_SIZE + LABEL_DEPTH)


def plain_zone(position: Sequence[int], name: str) -> Rect:
    """A node without notes: the node, or its name when that is wider, centred under it."""
    x, y = position
    width = max(NODE_SIZE, label_width(name))
    return Rect(x + (NODE_SIZE - width) // 2, y, width, NODE_SIZE + PLAIN_LABEL_DEPTH)


def stub_zone(position: Sequence[int]) -> Rect:
    """The "+" stub n8n draws right of an output that has no connection (Completed, Reject)."""
    x, y = position
    return Rect(x + STUB_X, y + STUB_Y, STUB_W, STUB_H)


def draws_forward(source_x: int, target_x: int) -> bool:
    """True when n8n draws the edge from the node at `source_x` to the one at `target_x` without a loop."""
    return (source_x + HANDLE_OUT) - BACKWARD_SLACK <= target_x + HANDLE_IN


def _control_offset(distance: float) -> float:
    """Vue Flow's `calculateControlOffset`: how far a bezier's control point sits from its handle."""
    return 0.5 * distance if distance >= 0 else CURVATURE * 25 * math.sqrt(-distance)


def false_edge(check: Sequence[int], reject: Sequence[int], samples: int = 64) -> list[tuple[float, float]]:
    """Points of the curve n8n draws from the check's `false` output to Reject's input (forward edges)."""
    sx, sy = check[0] + HANDLE_OUT, check[1] + FALSE_OUT_Y
    tx, ty = reject[0] + HANDLE_IN, reject[1] + INPUT_Y
    offset = _control_offset(tx - sx)
    xs, ys = (sx, sx + offset, tx - offset, tx), (sy, sy, ty, ty)
    weights = [
        ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2, t**3)
        for t in (i / samples for i in range(samples + 1))
    ]
    return [
        (sum(w * x for w, x in zip(ws, xs, strict=True)), sum(w * y for w, y in zip(ws, ys, strict=True)))
        for ws in weights
    ]


def bounds(rects: Iterable[Rect]) -> Rect:
    items = list(rects)
    left, top = min(r.x for r in items), min(r.y for r in items)
    return Rect(left, top, max(r.right for r in items) - left, max(r.bottom for r in items) - top)


def fit_zoom(canvas: Rect) -> float:
    """The zoom n8n's zoom to fit picks for `canvas` in a 1280 x 720 window."""
    return min(FIT_W / canvas.w, FIT_H / canvas.h)


def snap(value: float, step: int = GRID) -> int:
    """Round up to a multiple of `step` (n8n's 16 px grid by default)."""
    return math.ceil(value / step) * step


def snap_down(value: float, step: int = GRID) -> int:
    return math.floor(value / step) * step


def wrapped_lines(text: str, chars_per_line: int) -> int:
    """Lines a greedy word wrap needs for `text` at `chars_per_line` characters."""
    lines, used = 1, 0
    for word in text.split():
        need = len(word) if used == 0 else used + 1 + len(word)
        if need <= chars_per_line or used == 0:
            used = need
        else:
            lines, used = lines + 1, len(word)
    return lines


def _block_height(block: str, inner_width: int) -> float:
    kind = "h2" if block.startswith("## ") else "h3" if block.startswith("### ") else "p"
    char_w, line_h = METRICS[kind]
    lines = [MARKUP.sub("", line).lstrip("#").strip() for line in block.splitlines()]
    if all(re.match(r"^(-|\d+\.)\s", line) for line in lines):
        chars = int((inner_width - LIST_INDENT) / char_w)
        items = [re.sub(r"^(-|\d+\.)\s+", "", line) for line in lines]
        return sum(wrapped_lines(item, chars) * line_h + LIST_ITEM_GAP for item in items)
    chars = int(inner_width / char_w)
    return sum(wrapped_lines(line, chars) for line in lines) * line_h


def text_height(markdown: str, width: int) -> int:
    """Sticky height that shows all of `markdown` at `width` (blocks are separated by blank lines)."""
    inner = width - 2 * PAD_X - BORDER
    blocks = [block for block in markdown.split("\n\n") if block.strip()]
    body = sum(_block_height(block, inner) for block in blocks) + BLOCK_GAP * (len(blocks) - 1)
    return snap(PAD_TOP + body + SAFETY, SIZE_STEP)


@dataclass(frozen=True, slots=True)
class _Columns:
    left: int  # canvas left edge (title and security frame)
    split: int  # left edge of the checklist and failure notes
    right: int  # canvas right edge
    check: int
    reject: int
    steps: tuple[int, ...]
    done: int


def _columns(n_steps: int, names: RowNames) -> _Columns:
    """x of every node and frame edge; the row's y does not matter for any of them."""
    if n_steps < 1:
        raise ValueError("a workflow needs at least one step")
    check = SHORT_PITCH
    reject = check + REJECT_SHIFT
    left = snap_down(min(plain_zone((0, 0), names.webhook).x, check) - FRAME_PAD)
    security_right = max(
        plain_zone((check, 0), names.check).right,
        plain_zone((reject, 0), names.reject).right,
        stub_zone((reject, 0)).right,
    )
    split = snap(security_right + FRAME_PAD) + STICKY_GAP
    first = snap(split + FRAME_PAD + LABEL_OVERHANG)
    steps = tuple(first + PITCH * i for i in range(n_steps))
    last = first + PITCH * (max(n_steps, MIN_STEP_COLUMNS) - 1)  # the last step of the widest canvas
    edge = max(node_zone((last, 0)).right, plain_zone((last + SHORT_PITCH, 0), names.done).right)
    return _Columns(left, split, snap(edge + FRAME_PAD), check, reject, steps, steps[-1] + SHORT_PITCH)


def plan(n_steps: int, text: Markdown, names: RowNames) -> Layout:
    """Positions of the nodes and the sticky notes framing them."""
    cols = _columns(n_steps, names)
    title = Rect(cols.left, 0, cols.right - cols.left, text_height(text.title, cols.right - cols.left))
    top = title.bottom + STICKY_GAP
    security_w, checklist_w = cols.split - STICKY_GAP - cols.left, cols.right - cols.split
    text_h = max(text_height(text.security, security_w), text_height(text.checklist, checklist_w))
    row = snap(top + text_h + TEXT_GAP)
    reject_y = snap(row + NODE_SIZE + PLAIN_LABEL_DEPTH + REJECT_GAP)
    checklist = Rect(cols.split, top, checklist_w, snap(row + NODE_SIZE + LABEL_DEPTH + FRAME_PAD) - top)
    failure_top = checklist.bottom + STICKY_GAP
    bottom = snap(
        max(
            reject_y + NODE_SIZE + PLAIN_LABEL_DEPTH + FRAME_PAD,
            failure_top + text_height(text.failure, checklist_w),
        )
    )
    stickies = (
        Sticky("title", COLOR_TITLE, title, text.title),
        Sticky("security", COLOR_SECURITY, Rect(cols.left, top, security_w, bottom - top), text.security),
        Sticky("checklist", COLOR_CHECKLIST, checklist, text.checklist),
        Sticky(
            "failure",
            COLOR_FAILURE,
            Rect(cols.split, failure_top, checklist_w, bottom - failure_top),
            text.failure,
        ),
    )
    return Layout(
        webhook=(0, row),
        check=(cols.check, row),
        steps=tuple((x, row) for x in cols.steps),
        done=(cols.done, row),
        reject=(cols.reject, reject_y),
        stickies=stickies,
    )
