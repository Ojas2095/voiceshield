import asyncio
import json
import uuid
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.security.jwt import create_access_token
from backend.app.security.dependencies import register_call_ownership

# Helper to generate token for test user
def get_test_token(username: str = "test_user") -> str:
    return create_access_token(data={"sub": username}, expires_delta=timedelta(minutes=15))


collected_response_bodies = []


def record_response(response):
    collected_response_bodies.append(response.text)
    return response


def test_01_unauthenticated_request(client: TestClient):
    """Unauthenticated request to protected route returns 401."""
    res = client.get(f"/api/calls/{uuid.uuid4()}/status")
    record_response(res)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("[PASS] Test 01 Passed: Unauthenticated request -> 401")


def test_02_invalid_expired_jwt(client: TestClient):
    """Invalid or expired JWT returns 401."""
    headers = {"Authorization": "Bearer invalid.fake.jwt.token"}
    res = client.get(f"/api/calls/{uuid.uuid4()}/status", headers=headers)
    record_response(res)
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("[PASS] Test 02 Passed: Invalid/expired JWT -> 401")


def test_03_wrong_call_id_owner(client: TestClient):
    """Valid token but unauthorized caller (wrong owner) returns non-leaky 403 or 404."""
    # User A starts call
    token_a = get_test_token("user_a")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    start_res = client.post("/api/calls/start", json={"source": "mic"}, headers=headers_a)
    record_response(start_res)
    assert start_res.status_code == 200
    call_id = start_res.json()["call_id"]

    # User B attempts to access User A's call
    token_b = get_test_token("user_b")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    status_res = client.get(f"/api/calls/{call_id}/status", headers=headers_b)
    record_response(status_res)
    assert status_res.status_code in [403, 404], f"Expected 403/404, got {status_res.status_code}"
    print("[PASS] Test 03 Passed: Valid token but wrong call_id owner -> 403/404")


def test_04_malformed_call_id(client: TestClient):
    """Malformed call_id parameter returns 400 without DB traceback leak."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/calls/not-a-valid-uuid/stop", headers=headers)
    record_response(res)
    assert res.status_code in [400, 422], f"Expected 400/422, got {res.status_code}"
    assert "Traceback" not in res.text
    print("[PASS] Test 04 Passed: Malformed call_id -> 400/422 (no DB error leak)")


def test_05_invalid_source_value(client: TestClient):
    """Invalid source enum value returns 422 validation error."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/calls/start", json={"source": "invalid_audio_source"}, headers=headers)
    record_response(res)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"
    print("[PASS] Test 05 Passed: Invalid source value -> 422")


def test_06_oversized_ws_frame(client: TestClient):
    """Oversized WS frame (>64KB) is rejected/closed."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}"}
    start_res = client.post("/api/calls/start", json={"source": "mic"}, headers=headers)
    record_response(start_res)
    call_id = start_res.json()["call_id"]

    ws_rejected = False
    try:
        with client.websocket_connect(f"/ws/stream/{call_id}?token={token}") as websocket:
            oversized_payload = b"\x00" * (70 * 1024)
            websocket.send_bytes(oversized_payload)
            websocket.receive_json()
    except Exception:
        ws_rejected = True

    assert ws_rejected, "Oversized WS frame should have been rejected."
    print("[PASS] Test 06 Passed: Oversized WS frame -> rejected/closed")


def test_07_too_many_ws_connections(client: TestClient):
    """Duplicate WS connections to single call_id are rejected."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}"}
    start_res = client.post("/api/calls/start", json={"source": "mic"}, headers=headers)
    record_response(start_res)
    call_id = start_res.json()["call_id"]

    second_rejected = False
    with client.websocket_connect(f"/ws/stream/{call_id}?token={token}") as ws1:
        try:
            with client.websocket_connect(f"/ws/stream/{call_id}?token={token}") as ws2:
                pass
        except Exception:
            second_rejected = True

    assert second_rejected, "Second concurrent WS connection should have been rejected."
    print("[PASS] Test 07 Passed: Too many WS connections to one call_id -> rejected")


def test_08_ws_message_flood(client: TestClient):
    """Message flood exceeding rate limit is rejected/closed."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}"}
    start_res = client.post("/api/calls/start", json={"source": "mic"}, headers=headers)
    record_response(start_res)
    call_id = start_res.json()["call_id"]

    flood_rejected = False
    try:
        with client.websocket_connect(f"/ws/stream/{call_id}?token={token}") as ws:
            dummy_pcm = b"\x00" * 320
            for _ in range(70):
                ws.send_bytes(dummy_pcm)
            ws.receive_json()
    except Exception:
        flood_rejected = True

    assert flood_rejected, "WS message flood should have been rejected."
    print("[PASS] Test 08 Passed: WS message flood -> rejected/closed")


def test_09_double_stop_same_call(client: TestClient):
    """Stopping an already-ended call returns clean error, not crash."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}"}
    start_res = client.post("/api/calls/start", json={"source": "mic"}, headers=headers)
    record_response(start_res)
    call_id = start_res.json()["call_id"]

    # First stop
    stop1 = client.post(f"/api/calls/{call_id}/stop", headers=headers)
    record_response(stop1)
    assert stop1.status_code == 200

    # Second stop
    stop2 = client.post(f"/api/calls/{call_id}/stop", headers=headers)
    record_response(stop2)
    assert stop2.status_code == 400
    assert stop2.json().get("detail") == "Call is already ended"
    print("[PASS] Test 09 Passed: Double /stop on same call -> clean error not crash")


def test_10_malformed_json_body(client: TestClient):
    """Malformed JSON body returns 422 generic error."""
    token = get_test_token("user_a")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    res = client.post("/api/calls/start", content="{invalid_json:", headers=headers)
    record_response(res)
    assert res.status_code == 422, f"Expected 422, got {res.status_code}"
    print("[PASS] Test 10 Passed: Malformed JSON body -> 422 generic error")


def test_11_disallowed_cors_origin(client: TestClient):
    """Disallowed CORS origin does not return permissive headers."""
    headers = {"Origin": "http://evil-hacker-site.com"}
    res = client.get("/health", headers=headers)
    record_response(res)
    allow_origin = res.headers.get("access-control-allow-origin")
    assert allow_origin != "http://evil-hacker-site.com", f"Leaked disallowed origin: {allow_origin}"
    assert allow_origin != "*", "CORS wildcard allowed!"
    print("[PASS] Test 11 Passed: Disallowed CORS origin -> restricted")


def test_12_blanket_assertion_no_tracebacks():
    """Blanket assertion verifying no response body contains 'Traceback' or absolute file paths."""
    forbidden_keywords = ["Traceback", "File \"", "\\app\\", "/app/", ".py:"]
    for idx, body in enumerate(collected_response_bodies):
        for keyword in forbidden_keywords:
            assert keyword not in body, f"Leaked sensitive error detail '{keyword}' in response index {idx}: {body}"
    print("[PASS] Test 12 Passed: Blanket assertion (no Traceback or file path leakage across all responses).")


def run_security_proof_demo():
    print("\n=======================================================")
    print("     VOICESHIELD SECURITY DEMO PROOF SUITE RESULTS     ")
    print("=======================================================")
    with TestClient(app) as test_client:
        test_01_unauthenticated_request(test_client)
        test_02_invalid_expired_jwt(test_client)
        test_03_wrong_call_id_owner(test_client)
        test_04_malformed_call_id(test_client)
        test_05_invalid_source_value(test_client)
        test_06_oversized_ws_frame(test_client)
        test_07_too_many_ws_connections(test_client)
        test_08_ws_message_flood(test_client)
        test_09_double_stop_same_call(test_client)
        test_10_malformed_json_body(test_client)
        test_11_disallowed_cors_origin(test_client)
        test_12_blanket_assertion_no_tracebacks()
    print("-------------------------------------------------------")
    print(" SUMMARY: 12 / 12 SECURITY TESTS PASSED PERFECTLY (100%)")
    print("=======================================================\n")


if __name__ == "__main__":
    run_security_proof_demo()
