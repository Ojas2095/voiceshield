import asyncio
import os
import uuid
import pytest
from datetime import timedelta
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.main import app
from backend.app.db.base import Base
from backend.app.db.models import Call, Detection, EvidenceLog, TransactionHold
from backend.app.db.session import get_db
from backend.app.services.detections import insert_detection
from backend.app.security.jwt import create_access_token


TEST_DB_URL = "sqlite+aiosqlite:///./test_e2e_flow.db"
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Setup test database tables and teardown on test completion."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if os.path.exists("./test_e2e_flow.db"):
        try:
            os.remove("./test_e2e_flow.db")
        except Exception:
            pass


def get_auth_headers(username: str = "test_analyst") -> dict:
    token = create_access_token(data={"sub": username}, expires_delta=timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_full_e2e_flow_detect_prove_prevent_tamper():
    """
    End-to-End Verification of the Complete VoiceShield Data & Security Architecture:
    1. Start Call (source='replay')
    2. Sequentially ingest 3 detection windows (auto-generating SHA-256 evidence chain)
    3. GET /evidence -> assert chain_valid == True
    4. Mutate payload directly in DB (simulated tampering)
    5. GET /evidence -> assert chain_valid == False (tamper detected)
    6. POST /hold -> verify transaction hold created
    7. POST /hold again -> verify idempotency (returns existing hold without duplicating)
    """
    headers = get_auth_headers("analyst_akshat")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # STEP 1: Start a new call session
        start_res = await client.post("/api/calls/start", json={"source": "replay"}, headers=headers)
        assert start_res.status_code == 200, f"Start call failed: {start_res.text}"
        call_id = start_res.json()["call_id"]
        assert call_id is not None
        print(f"\n[E2E] 1. Call started successfully with call_id={call_id}")

        # STEP 2: Ingest 3 detection frames in sequence (atomically chaining evidence)
        async with TestSessionLocal() as session:
            d1 = await insert_detection(
                db=session,
                call_id=call_id,
                window_start_ms=0,
                window_end_ms=2000,
                spoof_probability=0.15,
                fused_risk_score=0.15,
                is_flagged=False,
                model_version="v0.1-dummy",
            )
            d2 = await insert_detection(
                db=session,
                call_id=call_id,
                window_start_ms=500,
                window_end_ms=2500,
                spoof_probability=0.88,
                fused_risk_score=0.515,
                is_flagged=False,
                model_version="v0.1-dummy",
            )
            d3 = await insert_detection(
                db=session,
                call_id=call_id,
                window_start_ms=1000,
                window_end_ms=3000,
                spoof_probability=0.92,
                fused_risk_score=0.75,
                is_flagged=True,
                model_version="v0.1-dummy",
            )
            det_id_1, det_id_2, det_id_3 = d1.detection_id, d2.detection_id, d3.detection_id

        print(f"[E2E] 2. Ingested 3 detections (IDs: {det_id_1}, {det_id_2}, {det_id_3}) with atomic evidence logs.")

        # STEP 3: Query Evidence API & verify cryptographic hash-chain
        ev_res = await client.get(f"/api/calls/{call_id}/evidence", headers=headers)
        assert ev_res.status_code == 200, f"Evidence query failed: {ev_res.text}"
        ev_data = ev_res.json()

        assert ev_data["call_id"] == call_id
        assert ev_data["chain_valid"] is True, "Expected intact evidence hash-chain to verify as True"
        assert len(ev_data["entries"]) == 3
        
        # Verify prev_hash linkage
        assert ev_data["entries"][0]["prev_hash"] == "0" * 64
        assert ev_data["entries"][1]["prev_hash"] == ev_data["entries"][0]["entry_hash"]
        assert ev_data["entries"][2]["prev_hash"] == ev_data["entries"][1]["entry_hash"]
        print("[E2E] 3. GET /evidence verified: chain_valid == TRUE across 3 chained blocks.")

        # STEP 4: Simulate malicious DB tampering
        # Directly mutate entry 2's payload in database to forge spoof_probability
        tampered_entry_id = ev_data["entries"][1]["entry_id"]
        async with TestSessionLocal() as session:
            stmt = select(EvidenceLog).where(EvidenceLog.entry_id == tampered_entry_id)
            result = await session.execute(stmt)
            entry_to_tamper = result.scalar_one()
            
            # Tamper the stored JSON payload
            mutated_payload = dict(entry_to_tamper.payload)
            mutated_payload["spoof_probability"] = 0.02  # Adversary lowered spoof score
            mutated_payload["is_flagged"] = False
            
            entry_to_tamper.payload = mutated_payload
            await session.commit()

        print(f"[E2E] 4. Directly mutated evidence_log entry {tampered_entry_id} in DB to simulate tampering.")

        # STEP 5: Query Evidence API again -> must detect tampering!
        ev_tampered_res = await client.get(f"/api/calls/{call_id}/evidence", headers=headers)
        assert ev_tampered_res.status_code == 200
        ev_tampered_data = ev_tampered_res.json()
        assert ev_tampered_data["chain_valid"] is False, "Cryptographic audit must detect tampered payload!"
        print("[E2E] 5. GET /evidence re-verified after tampering: chain_valid == FALSE (Tamper Successfully Detected!).")

        # STEP 6: Execute PREVENT hold
        hold_res = await client.post(
            f"/api/calls/{call_id}/hold",
            json={"triggered_by": det_id_3},
            headers=headers,
        )
        assert hold_res.status_code == 200, f"Hold request failed: {hold_res.text}"
        hold_data = hold_res.json()
        assert hold_data["call_id"] == call_id
        assert hold_data["mock_reference"].startswith("MOCK-")
        first_hold_id = hold_data["hold_id"]
        first_mock_ref = hold_data["mock_reference"]
        print(f"[E2E] 6. POST /hold successful: hold_id={first_hold_id}, mock_reference={first_mock_ref}")

        # STEP 7: Verify Idempotency on duplicate /hold calls
        hold_dup_res = await client.post(
            f"/api/calls/{call_id}/hold",
            json={"triggered_by": det_id_3},
            headers=headers,
        )
        assert hold_dup_res.status_code == 200
        hold_dup_data = hold_dup_res.json()
        assert hold_dup_data["hold_id"] == first_hold_id, "Idempotent hold must return identical hold_id"
        assert hold_dup_data["mock_reference"] == first_mock_ref, "Idempotent hold must return identical mock_ref"

        # Verify DB has exactly 1 hold record for this call
        async with TestSessionLocal() as session:
            count_stmt = select(TransactionHold).where(TransactionHold.call_id == uuid.UUID(call_id))
            count_res = await session.execute(count_stmt)
            all_holds = count_res.scalars().all()
            assert len(all_holds) == 1, f"Expected exactly 1 hold row in DB, found {len(all_holds)}"

        print("[E2E] 7. POST /hold duplicate verified: strictly idempotent (0 duplicate DB rows).")
        print("\n=================================================================")
        print("  ALL E2E DEMO PHASES PASSED (DETECT -> PREVENT -> PROVE -> TAMPER)")
        print("=================================================================\n")
