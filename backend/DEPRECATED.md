# ⚠️ `backend/` is DEPRECATED — use `backend_v2/`

This is the original prototype backend. The project's canonical backend is
**[`backend_v2/`](../backend_v2/)** — it's what the README, the frontend, the
trained model, the telephony DSP (µ-law/G.711), Silero VAD, and the
Ed25519-signed evidence chain all target.

**Do not run or wire the demo to `backend/`.** Run:

```bash
$env:PYTHONPATH="backend_v2"      # PowerShell (export on Linux/macOS)
python -m uvicorn app.main:app --port 8000 --reload
```

`backend/` is kept only for reference — it contains a JWT-auth/rate-limiting
security suite that has not yet been ported to `backend_v2`. If that hardening
is needed for production, port it into `backend_v2` rather than reviving this tree.
