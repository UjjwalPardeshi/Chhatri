"""Tests for memory integration (SPEC §14.6, §16)."""

from datetime import datetime, timedelta, timezone

import pytest

from chhatri.integrations.base import MemoryFact
from chhatri.integrations.memory import SimulatedMemoryGraph

IST = timezone(timedelta(hours=5, minutes=30))


class TestSimulatedMemoryGraph:
    """Tests for SimulatedMemoryGraph."""

    @pytest.mark.asyncio
    async def test_remember_fact(self):
        """Test storing a memory fact."""
        graph = SimulatedMemoryGraph()
        now = datetime.now(tz=IST)

        fact = MemoryFact(
            kind="payout",
            subject_id="P-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=now,
            text="Paid ₹1,380 for area claim",
        )

        await graph.remember(fact)

        # Verify node was created
        assert "P-000001" in graph.graph.nodes
        node_data = graph.graph.nodes["P-000001"]
        assert node_data["kind"] == "payout"
        assert node_data["text"] == "Paid ₹1,380 for area claim"

    @pytest.mark.asyncio
    async def test_remember_creates_edges(self):
        """Test that remember creates edges to merchant and zone."""
        graph = SimulatedMemoryGraph()
        now = datetime.now(tz=IST)

        fact = MemoryFact(
            kind="payout",
            subject_id="P-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=now,
            text="Paid",
        )

        await graph.remember(fact)

        # Check merchant and zone nodes exist
        assert "merchant:S-0142" in graph.graph.nodes
        assert "zone:Z7" in graph.graph.nodes

    @pytest.mark.asyncio
    async def test_precedents_empty(self):
        """Test precedents with empty graph."""
        graph = SimulatedMemoryGraph()

        precedents = await graph.precedents(merchant_id="S-0142", limit=5)
        assert len(precedents) == 0

    @pytest.mark.asyncio
    async def test_precedents_same_merchant_highest_score(self):
        """Test that same merchant has score 1.0."""
        graph = SimulatedMemoryGraph()
        base_time = datetime.now(tz=IST)

        # Add facts for different merchants
        fact1 = MemoryFact(
            kind="payout",
            subject_id="P-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=base_time - timedelta(days=2),
            text="First payout",
        )
        fact2 = MemoryFact(
            kind="payout",
            subject_id="P-000002",
            merchant_id="S-0143",
            zone_id="Z7",
            at=base_time - timedelta(days=1),
            text="Other merchant payout",
        )

        await graph.remember(fact1)
        await graph.remember(fact2)

        # Query precedents for S-0142
        precedents = await graph.precedents(merchant_id="S-0142")

        # Should return only S-0142's facts with score 1.0
        assert len(precedents) == 1
        assert precedents[0].subject_id == "P-000001"
        assert precedents[0].score == 1.0

    @pytest.mark.asyncio
    async def test_precedents_same_zone_score_0_7(self):
        """Test that same zone (no merchant match) has score 0.7."""
        graph = SimulatedMemoryGraph()
        base_time = datetime.now(tz=IST)

        # Add facts for different merchants, same zone
        fact = MemoryFact(
            kind="payout",
            subject_id="P-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=base_time,
            text="Z7 payout",
        )

        await graph.remember(fact)

        # Query precedents for Z7 (different merchant)
        precedents = await graph.precedents(zone_id="Z7", limit=5)

        # Should return Z7 fact with score 0.7
        assert len(precedents) == 1
        assert precedents[0].subject_id == "P-000001"
        assert precedents[0].score == 0.7

    @pytest.mark.asyncio
    async def test_precedents_recency_ordering(self):
        """Test that facts are ordered by recency (latest first)."""
        graph = SimulatedMemoryGraph()
        base_time = datetime.now(tz=IST)

        # Add facts at different times
        fact1 = MemoryFact(
            kind="payout",
            subject_id="P-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=base_time - timedelta(days=2),
            text="Oldest",
        )
        fact2 = MemoryFact(
            kind="payout",
            subject_id="P-000002",
            merchant_id="S-0142",
            zone_id="Z7",
            at=base_time,
            text="Newest",
        )

        await graph.remember(fact1)
        await graph.remember(fact2)

        precedents = await graph.precedents(merchant_id="S-0142")

        # Should be ordered by recency (newest first)
        assert len(precedents) == 2
        assert precedents[0].subject_id == "P-000002"
        assert precedents[1].subject_id == "P-000001"

    @pytest.mark.asyncio
    async def test_precedents_limit(self):
        """Test limit parameter."""
        graph = SimulatedMemoryGraph()
        base_time = datetime.now(tz=IST)

        # Add 5 facts
        for i in range(5):
            fact = MemoryFact(
                kind="payout",
                subject_id=f"P-{i:06d}",
                merchant_id="S-0142",
                zone_id="Z7",
                at=base_time - timedelta(days=i),
                text=f"Payout {i}",
            )
            await graph.remember(fact)

        # Query with limit=2
        precedents = await graph.precedents(merchant_id="S-0142", limit=2)

        # Should return only 2 results
        assert len(precedents) == 2

    @pytest.mark.asyncio
    async def test_precedents_kind_filter(self):
        """Test filtering by kind."""
        graph = SimulatedMemoryGraph()
        now = datetime.now(tz=IST)

        # Add facts of different kinds
        payout_fact = MemoryFact(
            kind="payout",
            subject_id="P-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=now,
            text="Payout",
        )
        dispute_fact = MemoryFact(
            kind="dispute",
            subject_id="D-000001",
            merchant_id="S-0142",
            zone_id="Z7",
            at=now,
            text="Dispute",
        )

        await graph.remember(payout_fact)
        await graph.remember(dispute_fact)

        # Query only payouts
        precedents = await graph.precedents(kind="payout")

        # Should return only payout fact
        assert len(precedents) == 1
        assert precedents[0].kind == "payout"
