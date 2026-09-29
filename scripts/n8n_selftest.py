#!/usr/bin/env python3
"""
Chhatri n8n workflow self-test (SPEC §14.5, §23)

Tests n8n workflow definitions by:
1. Running a mock backend server that listens to /internal/workflows/{step}
2. Verifying X-Chhatri-Secret header
3. Recording step calls in order
4. Posting to n8n webhooks (via N8N_BASE_URL)
5. Asserting steps arrive in the correct order

Usage:
    python scripts/n8n_selftest.py

Environment:
    N8N_BASE_URL: n8n base URL (default: http://localhost:5678)
    CHHATRI_INTERNAL_SECRET: shared secret (will be auto-set in test)
    CHHATRI_PUBLIC_URL: backend URL (will point to mock server)

Workflows tested:
    - chhatri-payout: execute_payout -> credit_payout -> notify_merchant -> pause_instalment
    - chhatri-human-review: open_case -> notify_officer
    - chhatri-follow-up: wait (24h configured as 0s for test) -> check_case_sla
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
CHHATRI_INTERNAL_SECRET = "test-secret-key"
MOCK_BACKEND_PORT = 9999
MOCK_BACKEND_URL = f"http://127.0.0.1:{MOCK_BACKEND_PORT}"

# Recorded workflow calls
recorded_calls: list[dict[str, Any]] = []
lock = threading.Lock()


@dataclass
class WorkflowTest:
    """Test case for a workflow."""
    name: str
    webhook_path: str
    payload: dict[str, str]
    expected_steps: list[str]
    delay: float = 0.5  # seconds between checks


def record_call(workflow: str, step: str, run_id: str, payload: dict) -> None:
    """Record a workflow step call."""
    with lock:
        recorded_calls.append({
            "workflow": workflow,
            "step": step,
            "run_id": run_id,
            "payload": payload,
            "timestamp": time.time()
        })
        logger.info(f"  ✓ {workflow}/{step} called")


class MockBackendHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock backend /internal/workflows/<step> endpoints."""

    def do_POST(self):
        """Handle POST to /internal/workflows/<step>."""
        # Verify path
        if not self.path.startswith("/internal/workflows/"):
            self.send_error(404, "Not Found")
            return

        step = self.path.split("/")[-1]

        # Verify secret header
        secret = self.headers.get("X-Chhatri-Secret", "")
        if secret != CHHATRI_INTERNAL_SECRET:
            logger.warning(f"  ✗ Invalid secret for {step}")
            self.send_error(403, "Invalid secret")
            return

        # Parse body
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"  ✗ Invalid JSON body: {e}")
            self.send_error(400, "Invalid JSON")
            return

        # Verify body shape
        required = {"run_id", "workflow", "step", "payload"}
        if not required.issubset(data.keys()):
            logger.warning(f"  ✗ Missing fields: {required - set(data.keys())}")
            self.send_error(400, "Missing required fields")
            return

        # Record call
        record_call(data["workflow"], data["step"], data["run_id"], data["payload"])

        # Respond 200
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        response = json.dumps({"ok": True, "data": {"step": step, "status": "done"}})
        self.wfile.write(response.encode())

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


def start_mock_backend() -> threading.Thread:
    """Start mock backend server in a thread."""
    server = HTTPServer(("127.0.0.1", MOCK_BACKEND_PORT), MockBackendHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Mock backend listening on {MOCK_BACKEND_URL}")
    return thread


def post_to_webhook(workflow_name: str, payload: dict) -> bool:
    """POST to n8n webhook and return success."""
    url = f"{N8N_BASE_URL}/webhook/chhatri-{workflow_name}"
    headers = {
        "X-Chhatri-Secret": CHHATRI_INTERNAL_SECRET,
        "Content-Type": "application/json"
    }
    body = json.dumps(payload).encode("utf-8")

    try:
        req = Request(url, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=5) as response:
            status = response.status
            logger.info(f"  → n8n webhook responded: {status}")
            return status in (200, 202)
    except URLError as e:
        logger.error(f"  ✗ Failed to reach n8n: {e}")
        return False
    except Exception as e:
        logger.error(f"  ✗ Unexpected error: {e}")
        return False


def wait_for_calls(run_id: str, expected_count: int, timeout: float = 10.0) -> list[dict[str, Any]]:
    """Wait for expected number of calls to arrive."""
    start = time.time()
    while time.time() - start < timeout:
        with lock:
            calls = [c for c in recorded_calls if c.get("run_id") == run_id]
        if len(calls) >= expected_count:
            return calls
        time.sleep(0.1)
    return calls


def test_workflow(test: WorkflowTest) -> bool:
    """Test a single workflow."""
    logger.info(f"\nTesting: {test.name}")
    logger.info(f"  Webhook: POST {N8N_BASE_URL}/webhook/{test.webhook_path}")

    # Generate run ID
    run_id = f"test-run-{int(time.time() * 1000)}"

    # POST to webhook
    payload = {"run_id": run_id, **test.payload}
    if not post_to_webhook(test.webhook_path.replace("chhatri-", ""), payload):
        logger.error(f"  ✗ Failed to post to webhook")
        return False

    # Wait for steps to be called
    calls = wait_for_calls(run_id, len(test.expected_steps), timeout=15.0)

    # Verify order
    actual_steps = [c["step"] for c in calls]
    if actual_steps != test.expected_steps:
        logger.error(f"  ✗ Step order mismatch")
        logger.error(f"    Expected: {test.expected_steps}")
        logger.error(f"    Got:      {actual_steps}")
        return False

    logger.info(f"  ✓ All {len(test.expected_steps)} steps arrived in correct order")
    return True


def main() -> int:
    """Run all workflow tests."""
    logger.info("Chhatri n8n workflow self-test")
    logger.info("=" * 50)

    # Check n8n connectivity
    logger.info(f"\nChecking n8n at {N8N_BASE_URL}...")
    try:
        req = Request(f"{N8N_BASE_URL}/healthz", method="GET")
        with urlopen(req, timeout=3) as response:
            if response.status != 200:
                logger.warning(f"  ⚠ n8n health check returned {response.status}")
    except Exception as e:
        logger.error(f"  ✗ Cannot reach n8n: {e}")
        logger.error(f"  Ensure n8n is running at {N8N_BASE_URL}")
        logger.error(f"  Tip: docker compose --profile n8n up")
        return 1

    logger.info(f"  ✓ n8n is reachable")

    # Start mock backend
    logger.info(f"\nStarting mock backend...")
    start_mock_backend()
    time.sleep(0.5)

    # Define tests
    tests = [
        WorkflowTest(
            name="Payout workflow",
            webhook_path="chhatri-payout",
            payload={
                "workflow": "payout",
                "payload": {"decision_id": "D-000001", "merchant_id": "S-0142"}
            },
            expected_steps=["execute_payout", "credit_payout", "notify_merchant", "pause_instalment"]
        ),
        WorkflowTest(
            name="Human review workflow",
            webhook_path="chhatri-human-review",
            payload={
                "workflow": "human-review",
                "payload": {"case_id": "C-2291", "merchant_id": "S-0142"}
            },
            expected_steps=["open_case", "notify_officer"]
        ),
        WorkflowTest(
            name="Follow-up workflow",
            webhook_path="chhatri-follow-up",
            payload={
                "workflow": "follow-up",
                "payload": {"case_id": "C-2291"}
            },
            expected_steps=["check_case_sla"]  # Wait step is not a backend call
        ),
    ]

    # Run tests
    logger.info(f"\nRunning workflow tests...")
    results = []
    for test in tests:
        results.append(test_workflow(test))

    # Summary
    logger.info(f"\n{'=' * 50}")
    passed = sum(results)
    total = len(results)
    logger.info(f"Results: {passed}/{total} tests passed")

    if passed == total:
        logger.info("✓ All n8n workflows are working correctly!")
        return 0
    else:
        logger.error(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
