"""Memory integration (SPEC §14.6, §16).

Simulated memory uses networkx. Live memory optionally uses Cognee.
"""

from __future__ import annotations

import logging
from datetime import datetime

import networkx as nx

from chhatri.integrations.base import IntegrationError, MemoryFact, Precedent

logger = logging.getLogger(__name__)


class SimulatedMemoryGraph:
    """In-memory fact store using networkx MultiDiGraph.

    Node types: shop, zone, event, payout, dispute, case, decision.
    Edge types: IN_ZONE, PAID_FOR, DISPUTED, DECIDED_BY, SIMILAR_TO.
    """

    def __init__(self) -> None:
        """Initialize with an empty networkx MultiDiGraph."""
        self.graph = nx.MultiDiGraph()

    async def remember(self, fact: MemoryFact) -> None:
        """Store a memory fact in the graph.

        Args:
            fact: The memory fact to store.
        """
        # Add the subject node if not present
        subject_node = fact.subject_id
        self.graph.add_node(subject_node, kind=fact.kind, at=fact.at, text=fact.text)

        # Add merchant and zone nodes if provided, with edges
        if fact.merchant_id:
            merchant_node = f"merchant:{fact.merchant_id}"
            self.graph.add_node(merchant_node, type="merchant")
            self.graph.add_edge(subject_node, merchant_node, relation="for_merchant")

        if fact.zone_id:
            zone_node = f"zone:{fact.zone_id}"
            self.graph.add_node(zone_node, type="zone")
            self.graph.add_edge(subject_node, zone_node, relation="in_zone")

    async def precedents(
        self,
        *,
        merchant_id: str | None = None,
        zone_id: str | None = None,
        kind: str | None = None,
        limit: int = 5,
    ) -> list[Precedent]:
        """Find similar past facts.

        Ranking:
        - Same merchant: 1.0
        - Same zone: 0.7
        - Other: 0.4
        - Ties broken by most recent (latest first)
        - Subject itself is excluded

        Args:
            merchant_id: Filter by merchant (optional).
            zone_id: Filter by zone (optional).
            kind: Filter by fact kind (optional).
            limit: Maximum number of results to return.

        Returns:
            List of Precedents sorted by score (descending) and recency.
        """
        precedents_list: list[tuple[str, datetime, str, float]] = []

        # Collect all nodes that might match the criteria
        for node in self.graph.nodes():
            if not isinstance(node, str):
                continue

            node_data = self.graph.nodes[node]
            node_kind = node_data.get("kind")
            node_at = node_data.get("at")
            node_text = node_data.get("text", "")

            # Skip if kind doesn't match filter
            if kind and node_kind != kind:
                continue

            # Calculate relevance score
            score = 0.4  # default: other
            node_merchant = self._get_connected_merchant(node)
            node_zone = self._get_connected_zone(node)

            if merchant_id and node_merchant == merchant_id:
                score = 1.0
            elif zone_id and node_zone == zone_id:
                score = 0.7
            elif merchant_id or zone_id:
                # If filtering by merchant/zone but this node doesn't match, skip
                continue

            if node_at:
                precedents_list.append((node, node_at, node_text, score))

        # Sort by score (descending) then by recency (latest first)
        precedents_list.sort(key=lambda x: (-x[3], -x[1].timestamp()))

        # Convert to Precedent objects
        result = [
            Precedent(
                subject_id=subject_id,
                kind=self.graph.nodes[subject_id].get("kind", "unknown"),
                at=at,
                text=text,
                score=score,
            )
            for subject_id, at, text, score in precedents_list[:limit]
        ]

        return result

    def _get_connected_merchant(self, node: str) -> str | None:
        """Get the merchant connected to a node."""
        for _, neighbor, _data in self.graph.out_edges(node, data=True):
            if neighbor.startswith("merchant:"):
                return neighbor.replace("merchant:", "")
        return None

    def _get_connected_zone(self, node: str) -> str | None:
        """Get the zone connected to a node."""
        for _, neighbor, _data in self.graph.out_edges(node, data=True):
            if neighbor.startswith("zone:"):
                return neighbor.replace("zone:", "")
        return None


class CogneeMemoryGraph:
    """Live memory using Cognee (if installed and configured).

    SPEC §0.1: Cognee memory is never live if COGNEE_ENABLED != true or cognee is not installed.
    """

    def __init__(self) -> None:
        """Initialize with lazy import of cognee.

        Raises:
            IntegrationError: If cognee is not installed or not properly configured.
        """
        try:
            import cognee  # type: ignore
        except ImportError:
            raise IntegrationError(
                "cognee",
                "cognee not installed",
            ) from None

        self.cognee = cognee

    async def remember(self, fact: MemoryFact) -> None:
        """Store a memory fact via Cognee.

        Args:
            fact: The memory fact to store.

        Raises:
            IntegrationError: If the Cognee operation fails.
        """
        try:
            # Convert fact to a structured format for Cognee
            fact_text = f"{fact.kind}: {fact.text}"
            metadata: dict[str, str] = {}

            if fact.merchant_id:
                fact_text += f" (merchant: {fact.merchant_id})"
                metadata["merchant_id"] = fact.merchant_id

            if fact.zone_id:
                fact_text += f" (zone: {fact.zone_id})"
                metadata["zone_id"] = fact.zone_id

            metadata["kind"] = fact.kind
            metadata["at"] = fact.at.isoformat()

            # Call cognee.add with the fact
            await self.cognee.add(fact_text, metadata=metadata)
        except Exception as e:
            raise IntegrationError(
                "cognee",
                f"Failed to store fact in Cognee: {type(e).__name__}",
                retryable=True,
            ) from e

    async def precedents(
        self,
        *,
        merchant_id: str | None = None,
        zone_id: str | None = None,
        kind: str | None = None,
        limit: int = 5,
    ) -> list[Precedent]:
        """Search for similar facts via Cognee.

        Args:
            merchant_id: Filter by merchant (optional).
            zone_id: Filter by zone (optional).
            kind: Filter by fact kind (optional).
            limit: Maximum number of results to return.

        Returns:
            List of Precedents from Cognee search.

        Raises:
            IntegrationError: If the search fails.
        """
        try:
            # Build a search query from the filters
            search_query = []
            if kind:
                search_query.append(kind)
            if merchant_id:
                search_query.append(f"merchant:{merchant_id}")
            if zone_id:
                search_query.append(f"zone:{zone_id}")

            query_str = " ".join(search_query) if search_query else "precedent"

            # Call cognee.search
            results = await self.cognee.search(query_str, limit=limit)

            # Convert results to Precedent objects
            precedents_list: list[Precedent] = []
            for result in results:
                # Extract timestamp from result if available
                at_str = result.get("metadata", {}).get("at")
                at = datetime.fromisoformat(at_str) if at_str else datetime.now()

                precedent = Precedent(
                    subject_id=result.get("id", "unknown"),
                    kind=result.get("metadata", {}).get("kind", "unknown"),
                    at=at,
                    text=result.get("text", ""),
                    score=result.get("score", 0.5),
                )
                precedents_list.append(precedent)

            return precedents_list
        except Exception as e:
            raise IntegrationError(
                "cognee",
                f"Failed to search Cognee: {type(e).__name__}",
                retryable=True,
            ) from e
