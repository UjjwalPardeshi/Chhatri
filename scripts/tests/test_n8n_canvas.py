"""Canvas geometry: sticky sizes fit their text, frames hold their nodes, nothing overlaps."""

from __future__ import annotations

import pytest

import n8n_canvas as canvas

WORDS = "Every run must carry the shared secret in its header. " * 6
TEXT = canvas.Markdown(
    title="## A title\n\n" + WORDS,
    security="### Security check\n\n" + WORDS,
    checklist="### Checklist\n\n1. **One** · +0 min: first\n2. **Two** · +4 min: second\n\nThen done.",
    failure="### If a step fails\n\n- " + WORDS + "\n- short",
)


def test_rect_overlap_and_containment() -> None:
    a = canvas.Rect(0, 0, 100, 100)
    assert a.right == 100 and a.bottom == 100
    assert a.overlaps(canvas.Rect(50, 50, 100, 100))
    assert not a.overlaps(canvas.Rect(100, 0, 10, 10))  # touching edges do not overlap
    assert a.contains(canvas.Rect(10, 10, 80, 90)) and not a.contains(canvas.Rect(10, 10, 95, 10))


def test_node_zone_includes_the_name_under_the_node() -> None:
    assert canvas.node_zone((220, 400)) == canvas.Rect(170, 400, 200, 100 + canvas.LABEL_DEPTH)
    assert canvas.node_zone((0, 0), canvas.PLAIN_LABEL_DEPTH).h == 100 + canvas.PLAIN_LABEL_DEPTH


def test_snap_rounds_up() -> None:
    assert canvas.snap(0) == 0 and canvas.snap(1) == 20 and canvas.snap(40) == 40
    assert canvas.snap(41, 10) == 50


def test_wrapped_lines() -> None:
    assert canvas.wrapped_lines("", 10) == 1
    assert canvas.wrapped_lines("one two three", 13) == 1
    assert canvas.wrapped_lines("one two three", 7) == 2
    assert canvas.wrapped_lines("averyveryverylongword x", 5) == 2  # a long word takes a line of its own


def test_text_height_grows_with_text_and_shrinks_with_width() -> None:
    short = canvas.text_height("### Head\n\nA line.", 400)
    assert short >= canvas.PAD_TOP + 22 + 19 and short % canvas.SIZE_STEP == 0
    assert canvas.text_height("### Head\n\n" + WORDS, 400) > short
    assert canvas.text_height(WORDS, 300) > canvas.text_height(WORDS, 900)
    listed = canvas.text_height("- " + WORDS + "\n- b", 400)
    assert listed > canvas.text_height(WORDS, 400)
    assert canvas.text_height("## Big title", 900) > canvas.text_height("### Big title", 900)


@pytest.mark.parametrize("n_steps", [1, 2, 3, 4, 5, 7])
def test_plan_frames_every_node_without_overlap(n_steps: int) -> None:
    layout = canvas.plan(n_steps, TEXT)
    sticky = {s.key: s for s in layout.stickies}
    assert set(sticky) == {"title", "security", "checklist", "failure"}
    rects = [s.rect for s in layout.stickies]
    assert not [(a, b) for i, a in enumerate(rects) for b in rects[i + 1 :] if a.overlaps(b)]
    zones = {
        "webhook": canvas.node_zone(layout.webhook),
        "verify": canvas.node_zone(layout.verify),
        "done": canvas.node_zone(layout.done),
        "reject": canvas.node_zone(layout.reject, canvas.PLAIN_LABEL_DEPTH),
        **{f"step{i}": canvas.node_zone(p) for i, p in enumerate(layout.steps)},
    }
    expected_frame = {"webhook": "security", "verify": "security", "reject": "security", "done": "checklist"}
    for name, zone in zones.items():
        frame = sticky[expected_frame.get(name, "checklist")]
        assert frame.rect.contains(zone), name
        assert zone.y >= frame.rect.y + canvas.text_height(frame.content, frame.rect.w), name
        assert [s.key for s in layout.stickies if s.rect.overlaps(zone)] == [frame.key], name
    assert sticky["title"].rect.h >= canvas.text_height(TEXT.title, sticky["title"].rect.w)
    assert sticky["failure"].rect.h >= canvas.text_height(TEXT.failure, sticky["failure"].rect.w)
    assert sticky["failure"].rect.bottom == sticky["security"].rect.bottom
    assert (
        sticky["title"].rect.w == sticky["security"].rect.w + canvas.STICKY_GAP + sticky["checklist"].rect.w
    )


def test_plan_row_is_left_to_right_and_reject_is_below_the_check() -> None:
    layout = canvas.plan(4, TEXT)
    row = [layout.webhook, layout.verify, *layout.steps, layout.done]
    assert len({y for _, y in row}) == 1
    assert [x for x, _ in row] == [canvas.PITCH * i for i in range(len(row))]
    assert layout.reject[0] == layout.verify[0] and layout.reject[1] > layout.verify[1]


def test_plan_needs_a_step() -> None:
    with pytest.raises(ValueError, match="at least one step"):
        canvas.plan(0, TEXT)


def test_short_workflows_are_as_wide_as_four_steps() -> None:
    widths = {canvas.plan(n, TEXT).stickies[0].rect.w for n in (1, 2, 4)}
    assert len(widths) == 1
    assert canvas.plan(5, TEXT).stickies[0].rect.w > widths.pop()
