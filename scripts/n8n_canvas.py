"""Where everything sits on the n8n canvas of a Chhatri workflow (looks only, no behaviour).

Left to right on one row: webhook -> secret check -> step 1 .. step n -> Completed (200); the reject
branch sits below the secret check. Sticky notes frame their nodes, text on top, nodes below the text:

    +--------------------------- title: what starts it, n8n never decides --------------------------+
    +-- security (red) ---------+  +-- checklist (green): what each step does, simulated times -------+
    |  webhook -> secret check  |  |  step 1 -> step 2 -> ... -> Completed (200)                     |
    |             reject (403)  |  +-------------------------------------------------------------------+
    |                           |  +-- if a step fails (orange) --------------------------------------+
    +---------------------------+  +-------------------------------------------------------------------+

Sizes come from a conservative estimate of the rendered markdown (n8n 2.41.3 sticky styles: 14 px body
text, 24 px `##`, 16 px `###`, 8/12 px padding, overflow hidden), so no text is clipped; positions are
multiples of 20 (n8n's grid). The tests check that nothing overlaps and every node sits inside its frame,
below the frame's text.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

GRID: Final = 20  # node positions
SIZE_STEP: Final = 10  # sticky sizes
NODE_SIZE: Final = 100  # n8n draws regular nodes 100 x 100 at `position` (top-left corner)
PITCH: Final = 220  # node to node, left to right
LABEL_OVERHANG: Final = 50  # the name under a node is 200 px wide, centred on the node
LABEL_DEPTH: Final = 70  # two lines of name + one line of notes under the node
PLAIN_LABEL_DEPTH: Final = 50  # two lines of name, no notes (the reject node)
FRAME_PAD: Final = 10  # frame edge to the nearest node zone, above and below
STICKY_GAP: Final = 20  # between two sticky notes
TEXT_GAP: Final = 10  # frame text to the nodes below it
REJECT_GAP: Final = 30  # main row zone to the reject node
MIN_STEP_COLUMNS: Final = 4  # every canvas is as wide as payout's, so all three zoom alike

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
class Layout:
    webhook: tuple[int, int]
    verify: tuple[int, int]
    steps: tuple[tuple[int, int], ...]
    done: tuple[int, int]
    reject: tuple[int, int]
    stickies: tuple[Sticky, ...]


def node_zone(position: Sequence[int], depth: int = LABEL_DEPTH) -> Rect:
    """A node with the name (and notes) n8n draws under it."""
    x, y = position
    return Rect(x - LABEL_OVERHANG, y, NODE_SIZE + 2 * LABEL_OVERHANG, NODE_SIZE + depth)


def snap(value: float, step: int = GRID) -> int:
    """Round up to a multiple of `step` (n8n's 20 px grid by default)."""
    return math.ceil(value / step) * step


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


def _columns(n_steps: int) -> tuple[list[int], int, int]:
    """x of the step nodes, of Completed (200), and of the canvas' right edge."""
    if n_steps < 1:
        raise ValueError("a workflow needs at least one step")
    steps = [PITCH * (1 + i) for i in range(1, n_steps + 1)]
    right = PITCH * (max(n_steps, MIN_STEP_COLUMNS) + 2) + NODE_SIZE + LABEL_OVERHANG
    return steps, PITCH * (n_steps + 2), right


def plan(n_steps: int, text: Markdown) -> Layout:
    """Positions of the nodes and the sticky notes framing them."""
    step_xs, done_x, right = _columns(n_steps)
    left = -LABEL_OVERHANG
    split = step_xs[0] - LABEL_OVERHANG  # left edge of the checklist column
    title = Rect(left, 0, right - left, text_height(text.title, right - left))
    top = title.bottom + STICKY_GAP
    security_w, checklist_w = split - STICKY_GAP - left, right - split
    text_h = max(text_height(text.security, security_w), text_height(text.checklist, checklist_w))
    row = snap(top + text_h + TEXT_GAP)
    zone_bottom = row + NODE_SIZE + LABEL_DEPTH
    reject_y = snap(zone_bottom + REJECT_GAP)
    checklist = Rect(split, top, checklist_w, zone_bottom + FRAME_PAD - top)
    failure_top = checklist.bottom + STICKY_GAP
    bottom = max(
        reject_y + NODE_SIZE + PLAIN_LABEL_DEPTH + FRAME_PAD,
        failure_top + text_height(text.failure, checklist_w),
    )
    stickies = (
        Sticky("title", COLOR_TITLE, title, text.title),
        Sticky("security", COLOR_SECURITY, Rect(left, top, security_w, bottom - top), text.security),
        Sticky("checklist", COLOR_CHECKLIST, checklist, text.checklist),
        Sticky(
            "failure",
            COLOR_FAILURE,
            Rect(split, failure_top, checklist_w, bottom - failure_top),
            text.failure,
        ),
    )
    return Layout(
        webhook=(0, row),
        verify=(PITCH, row),
        steps=tuple((x, row) for x in step_xs),
        done=(done_x, row),
        reject=(PITCH, reject_y),
        stickies=stickies,
    )
