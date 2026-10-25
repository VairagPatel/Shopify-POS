# Eluno POS — pre-submission GitHub checklist

**Status:** Prepared only. No Git push, GitHub invitation, Loom recording or email submission has been performed.

## A. Confirm requirements and time

- [ ] Confirm the **actual email timestamp and deadline**. Email says 72 hours; attached exercise pack says 48 hours. We planned for 48 hours; do not infer a time of day from these documents.
- [ ] Ensure `STAKEHOLDER_REPLY.md` is included and is at most two pages when rendered. It is Part A and has equal grading weight to the code.
- [ ] Check that README states **what is actually built**, the exact setup, remaining gaps, and no UI.
- [ ] Open `DECISIONS.md` and be ready to discuss the key trade-offs; it is a supplementary engineering narrative, not a substitute for Part A.

## B. Local reproducibility (must check before push)

- [ ] From the repository root: `python -m pip install -r requirements.txt` in a clean Python 3.10+ environment, if available.
- [ ] Run `python exercise-pack/starter-kit/validate_seed.py` and observe success.
- [ ] In terminal 1: `python exercise-pack/starter-kit/mock-apis/mock_server.py --no-flake`.
- [ ] In terminal 2: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- [ ] Open `http://127.0.0.1:8000/docs`; demonstrate two-pair prepare, complete, refund and day-end report with synthetic fixtures.
- [ ] Run `python -m pytest -q`; latest verified result here was **35 passed in 13.24s** (24 Oct 2026), but rerun on your own machine.
- [ ] **Unresolved Must constraint:** the brief requests **one command after cloning**, while this version requires separate mock and app processes. Either fix and retest before submission or disclose the limitation accurately. Do not claim it passes as-is.
- [ ] Be aware: mock restart resets its state, SQLite does not. Use a fresh local DB for each **synthetic demo** and never erase an uncertain real payment history without reconciliation.

## C. What to commit, and what to exclude

- [ ] Include `README.md`, `STAKEHOLDER_REPLY.md`, `DECISIONS.md`, `LOOM_SCRIPT.md` (optional), `FINAL_AUDIT.md` (optional), `requirements.txt`, `app/`, `tests/`, and the exercise fixture/mock files needed to run locally.
- [ ] Check for no `.env`, credentials, access tokens, real customer details, `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, `runtime/`, `*.sqlite3`, logs, or local temporary files. The final package prepared here excludes cache directories; still check local Git status.
- [ ] Confirm `git status` and `git diff --check` are clean/understood. Inspect staged changes before any commit.
- [ ] Use a clear commit message, such as `Build mock-backed Eluno billing and refund flow`.
- [ ] Create a GitHub repository in **your own account**; choose private or public intentionally. No repository exists by virtue of this bundle.
- [ ] If private, invite **kaustabh.ghosh@longivitate.in** as stated in Eluno's email, and confirm access is accepted/available.
- [ ] Verify the repository link opens from a browser session allowed to access the repo. Check the default branch contains the correct files.

## D. Loom and final communication

- [ ] Use `LOOM_SCRIPT.md`; run **under 8 minutes**. Prefer ~7:35.
- [ ] Show Part A, architecture, **two-pair** sale with `SECONDPAIR50`, refund/restock, Shopify day-end, decisions, and **35 tests**.
- [ ] Explain 2–3 decisions you're glad you made, **one you'd revisit**, and accurately what AI helped with and where it misled you (only if true).
- [ ] Confirm recording audio/screen quality and Loom link access without needing permission.
- [ ] Include repo URL and Loom URL in the reply to the original exercise email; don't send until explicit final approval.
- [ ] Disclose material limits: single customer prescription across pairs, repeated-SKU rejection, manual uncertain-payment recovery, stock race, settlement report basis, and one-command run gap.

## E. Founder talking points

**Why no frontend?** The exercise permits a CLI or API; priority was validating financial rules and API behavior.

**Why local SQLite?** Persists invoice/checkout/refund state during mock development with little operational overhead; production needs a centrally managed DB.

**How did you prevent double charges?** Persist before calling external providers; halt on uncertain outcomes rather than repeat non-idempotent writes. This prevents automatic duplication from our flow, but human reconciliation is needed.

**Why positional pairing?** Deterministic and narrow for same-customer two-pair coverage; production needs explicit pair groups, quantities and wearer prescriptions.

**What would you revisit?** A single reliable launcher, terminal reconciliation, stock reservation and finance-grade refund-date reporting.

## Before taking any external action

**STOP.** Ask for explicit approval to push the repository, send GitHub invitations, record Loom, or send the final email. Preparation alone is authorized here.
