"""Canvas geometry: sticky sizes fit their text, frames hold their nodes, nothing overlaps, edges read cleanly."""

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
NAMES = canvas.RowNames(
    webhook="Chhatri webhook", check="Secret OK?", done="Completed (200)", reject="Reject (403)"
)


def test_rect_overlap_and_containment() -> None:
    a = canvas.Rect(0, 0, 100, 100)
    assert a.right == 100 and a.bottom == 100
    assert a.overlaps(canvas.Rect(50, 50, 100, 100))
    assert not a.overlaps(canvas.Rect(100, 0, 10, 10))  # touching edges do not overlap
    assert a.contains(canvas.Rect(10, 10, 80, 90)) and not a.contains(canvas.Rect(10, 10, 95, 10))


def test_node_zone_includes_the_name_and_notes_under_the_node() -> None:
    assert canvas.node_zone((224, 400)) == canvas.Rect(176, 400, 192, 96 + canvas.LABEL_DEPTH)


def test_stub_zone_is_the_plus_right_of_an_unconnected_output() -> None:
    """Measured in n8n 2.41.3: Completed (200) at (1392, 384) draws its "+" at 1496..1566 x 419..445."""
    assert canvas.stub_zone((1392, 384)) == canvas.Rect(1496, 419, 70, 26)


def test_label_width_is_conservative_and_capped_at_two_lines() -> None:
    assert canvas.label_width("Secret OK?") <= canvas.NODE_SIZE  # fits under its node
    assert canvas.label_width("Chhatri webhook") > canvas.label_width("Secret OK?")
    # n8n 2.41.3 draws "Verify X-Chhatri-Secret" about 178 px wide on one line
    assert 178 <= canvas.label_width("Verify X-Chhatri-Secret") <= canvas.LABEL_MAX
    assert canvas.label_width("x" * 80) == canvas.LABEL_MAX  # wraps to two lines in a 192 px box


def test_plain_zone_is_the_node_or_its_wider_name() -> None:
    assert canvas.plain_zone((224, 400), "Secret OK?") == canvas.Rect(
        224, 400, 96, 96 + canvas.PLAIN_LABEL_DEPTH
    )
    wide = canvas.plain_zone((0, 0), "Chhatri webhook")
    assert wide.w == canvas.label_width("Chhatri webhook") and wide.x + wide.w / 2 == canvas.NODE_SIZE / 2


def test_draws_forward_matches_n8n_2_41_3() -> None:
    """n8n draws a back-loop when sourceX - 20 > targetX (sourceX = x + 104, targetX = x - 8)."""
    check = 192
    assert not canvas.draws_forward(check, check)  # Reject straight below the check: the old loop
    assert not canvas.draws_forward(check, check + 80)
    assert canvas.draws_forward(check, check + canvas.REJECT_SHIFT)
    assert canvas.draws_forward(0, canvas.SHORT_PITCH)


def test_snap_rounds_to_the_grid() -> None:
    assert canvas.snap(0) == 0 and canvas.snap(1) == 16 and canvas.snap(32) == 32 and canvas.snap(33) == 48
    assert canvas.snap(41, 10) == 50 and canvas.snap_down(-21) == -32 and canvas.snap_down(17) == 16


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


def _zones(layout: canvas.Layout) -> dict[str, tuple[canvas.Rect, str]]:
    """Every node's zone and the sticky that must frame it."""
    return {
        "webhook": (canvas.plain_zone(layout.webhook, NAMES.webhook), "security"),
        "check": (canvas.plain_zone(layout.check, NAMES.check), "security"),
        "reject": (canvas.plain_zone(layout.reject, NAMES.reject), "security"),
        "done": (canvas.plain_zone(layout.done, NAMES.done), "checklist"),
        **{f"step{i}": (canvas.node_zone(p), "checklist") for i, p in enumerate(layout.steps)},
    }


@pytest.mark.parametrize("n_steps", [1, 2, 3, 4, 5, 7])
def test_plan_frames_every_node_without_overlap(n_steps: int) -> None:
    layout = canvas.plan(n_steps, TEXT, NAMES)
    sticky = {s.key: s for s in layout.stickies}
    assert set(sticky) == {"title", "security", "checklist", "failure"}
    rects = [s.rect for s in layout.stickies]
    assert not [(a, b) for i, a in enumerate(rects) for b in rects[i + 1 :] if a.overlaps(b)]
    zones = _zones(layout)
    zone_list = [zone for zone, _ in zones.values()]
    assert not [(a, b) for i, a in enumerate(zone_list) for b in zone_list[i + 1 :] if a.overlaps(b)]
    for name, (zone, frame_key) in zones.items():
        frame = sticky[frame_key]
        assert frame.rect.contains(zone), name
        assert zone.y >= frame.rect.y + canvas.text_height(frame.content, frame.rect.w), name
        assert [s.key for s in layout.stickies if s.rect.overlaps(zone)] == [frame.key], name
    for key in ("title", "failure"):
        assert sticky[key].rect.h >= canvas.text_height(sticky[key].content, sticky[key].rect.w)
    assert sticky["failure"].rect.bottom == sticky["security"].rect.bottom
    assert (
        sticky["title"].rect.w == sticky["security"].rect.w + canvas.STICKY_GAP + sticky["checklist"].rect.w
    )
    nodes = (layout.webhook, layout.check, layout.reject, layout.done, *layout.steps)
    assert all(v % canvas.GRID == 0 for p in nodes for v in p)  # n8n would snap them otherwise
    assert all(v % canvas.GRID == 0 for r in rects for v in (r.x, r.y, r.w, r.h))
    reject_stub, done_stub = canvas.stub_zone(layout.reject), canvas.stub_zone(layout.done)
    assert sticky["security"].rect.contains(reject_stub)
    assert [s.key for s in layout.stickies if s.rect.overlaps(reject_stub)] == ["security"]
    assert [s.key for s in layout.stickies if s.rect.overlaps(done_stub)] in (["checklist"], [])
    others = [zone for name, (zone, _) in zones.items() if name not in {"reject", "done"}]
    assert not [z for z in others if z.overlaps(reject_stub) or z.overlaps(done_stub)]


def test_plan_row_is_left_to_right_with_even_steps() -> None:
    layout = canvas.plan(4, TEXT, NAMES)
    row = [layout.webhook, layout.check, *layout.steps, layout.done]
    assert len({y for _, y in row}) == 1
    xs = [x for x, _ in row]
    gaps = [b - a for a, b in zip(xs, xs[1:], strict=False)]
    assert gaps[0] == gaps[-1] == canvas.SHORT_PITCH  # no notes line between those nodes
    assert set(gaps[2:-1]) == {canvas.PITCH}  # step to step
    assert gaps[1] >= canvas.PITCH  # the security frame ends between the check and step 1


def test_reject_branch_reads_forward_below_the_check() -> None:
    """The false edge leaves the check's right side and drops into Reject: no loop, no crossed label."""
    layout = canvas.plan(4, TEXT, NAMES)
    (check_x, check_y), (reject_x, reject_y) = layout.check, layout.reject
    assert canvas.draws_forward(check_x, reject_x)
    assert reject_x >= check_x + canvas.NODE_SIZE  # the edge passes right of the check's name ...
    assert canvas.label_width(NAMES.check) <= canvas.NODE_SIZE  # ... which is no wider than the node
    assert reject_y >= check_y + canvas.NODE_SIZE + canvas.PLAIN_LABEL_DEPTH  # below that name
    step1 = canvas.node_zone(layout.steps[0])
    assert canvas.plain_zone(layout.reject, NAMES.reject).right < step1.x


def test_false_edge_matches_the_path_n8n_draws() -> None:
    """n8n 2.41.3 drew `M296,432 C321,432 255,592 280,592` for the check at (192, 368), Reject at (288, 544)."""
    points = canvas.false_edge((192, 368), (288, 544), samples=2)
    assert points[0] == (296, 432) and points[-1] == (280, 592)
    assert points[1] == pytest.approx((0.125 * 296 + 0.375 * 321 + 0.375 * 255 + 0.125 * 280, 512))


@pytest.mark.parametrize("n_steps", [1, 2, 4])
def test_false_edge_passes_right_of_the_check_name(n_steps: int) -> None:
    """The check's name fits on one line under the node; the edge crosses that line's height to its right."""
    layout = canvas.plan(n_steps, TEXT, NAMES)
    (x, y), width = layout.check, canvas.label_width(NAMES.check)
    assert width <= canvas.NODE_SIZE  # one line
    name_right = x + canvas.NODE_SIZE / 2 + width / 2
    top, bottom = y + canvas.NODE_SIZE, y + canvas.NODE_SIZE + canvas.LABEL_TOP + canvas.LABEL_LINE
    band = [px for px, py in canvas.false_edge(layout.check, layout.reject) if top <= py <= bottom]
    assert band and min(band) >= name_right + 2
    reject = canvas.plain_zone(layout.reject, NAMES.reject)
    assert max(x for x, _ in canvas.false_edge(layout.check, layout.reject)) < reject.right


def test_plan_needs_a_step() -> None:
    with pytest.raises(ValueError, match="at least one step"):
        canvas.plan(0, TEXT, NAMES)


def test_short_workflows_are_as_wide_as_the_minimum() -> None:
    widths = {canvas.plan(n, TEXT, NAMES).stickies[0].rect.w for n in range(1, canvas.MIN_STEP_COLUMNS + 1)}
    assert len(widths) == 1
    assert canvas.plan(canvas.MIN_STEP_COLUMNS + 1, TEXT, NAMES).stickies[0].rect.w > widths.pop()


def test_fit_zoom_matches_n8n_measurements() -> None:
    """Zoom to fit at 1280 x 720 in n8n 2.41.3, measured on three rendered canvases."""
    assert canvas.fit_zoom(canvas.Rect(-48, 0, 1528, 794)) == pytest.approx(0.6499, abs=0.001)
    assert canvas.fit_zoom(canvas.Rect(-48, 0, 1528, 714)) == pytest.approx(0.6754, abs=0.001)
    assert canvas.fit_zoom(canvas.Rect(-32, 0, 1546, 774)) == pytest.approx(0.6667, abs=0.001)
    assert canvas.bounds([canvas.Rect(0, 0, 10, 10), canvas.Rect(-5, 20, 10, 10)]) == canvas.Rect(
        -5, 0, 15, 30
    )
