"""Tests for Paytm payment integration (SPEC §14.3)."""

import pytest

from chhatri.domain.enums import Language
from chhatri.domain.models import Merchant
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.paytm import McpPaytmLinks, SimulatedPaytmLinks


# Create a test merchant
TEST_MERCHANT = Merchant(
    id="S-0142",
    shop_name="Anil's Tea Stall",
    owner_name="Anil Jadhav",
    owner_name_hi="अनिल",
    kyc_name="ANIL RAMESH JADHAV",
    phone="+919900000001",
    language=Language.HI,
    zone_id="Z7",
    lat=19.0046,
    lng=72.8424,
    h3_cell="test",
    shop_type="TEA_STALL",
)


class TestSimulatedPaytmLinks:
    """Tests for SimulatedPaytmLinks."""

    @pytest.mark.asyncio
    async def test_create_link_deterministic(self):
        """Test that simulated links are deterministic."""
        paytm = SimulatedPaytmLinks()

        # Create same link twice
        link1 = await paytm.create_premium_link(TEST_MERCHANT, 100000, "Test Premium")
        link2 = await paytm.create_premium_link(TEST_MERCHANT, 100000, "Test Premium")

        assert link1.link_id == link2.link_id
        assert link1.url == link2.url
        assert link1.source == "simulated"

    @pytest.mark.asyncio
    async def test_create_link_format(self):
        """Test simulated link format."""
        paytm = SimulatedPaytmLinks()

        link = await paytm.create_premium_link(TEST_MERCHANT, 100000, "Test Premium")

        assert link.url.startswith("https://paytm.me/sim-")
        assert link.link_id.startswith("SIM-")
        assert link.amount_paise == 100000
        assert link.created_at is not None

    @pytest.mark.asyncio
    async def test_link_payment_unpaid(self):
        """Test that simulated links are initially unpaid."""
        paytm = SimulatedPaytmLinks()

        link = await paytm.create_premium_link(TEST_MERCHANT, 100000, "Test Premium")
        payment = await paytm.link_payment(link.link_id)

        assert payment.link_id == link.link_id
        assert payment.paid is False
        assert payment.txn_id is None

    @pytest.mark.asyncio
    async def test_create_different_amounts(self):
        """Test that different amounts produce different links."""
        paytm = SimulatedPaytmLinks()

        link1 = await paytm.create_premium_link(TEST_MERCHANT, 100000, "Premium")
        link2 = await paytm.create_premium_link(TEST_MERCHANT, 200000, "Premium")

        assert link1.link_id != link2.link_id
        assert link1.url != link2.url


class TestMcpPaytmLinks:
    """Tests for McpPaytmLinks."""

    def test_parse_paytm_response_valid(self):
        """Test parsing valid Paytm response."""
        response = "url =https://paytm.me/test123\nlinkId=LINK123"
        url, link_id = McpPaytmLinks._parse_paytm_response(response)

        assert url == "https://paytm.me/test123"
        assert link_id == "LINK123"

    def test_parse_paytm_response_with_whitespace(self):
        """Test parsing response with extra whitespace."""
        response = "url = https://paytm.me/test123 \nlinkId= LINK123 "
        url, link_id = McpPaytmLinks._parse_paytm_response(response)

        assert url == "https://paytm.me/test123"
        assert link_id == "LINK123"

    def test_parse_paytm_response_invalid(self):
        """Test parsing invalid response format."""
        response = "invalid response format"

        with pytest.raises(IntegrationError, match="Invalid response format"):
            McpPaytmLinks._parse_paytm_response(response)

    def test_parse_paytm_response_missing_url(self):
        """Test parsing response missing URL."""
        response = "linkId=LINK123"

        with pytest.raises(IntegrationError, match="Invalid response format"):
            McpPaytmLinks._parse_paytm_response(response)

    def test_parse_paytm_response_missing_link_id(self):
        """Test parsing response missing link ID."""
        response = "url =https://paytm.me/test123"

        with pytest.raises(IntegrationError, match="Invalid response format"):
            McpPaytmLinks._parse_paytm_response(response)
