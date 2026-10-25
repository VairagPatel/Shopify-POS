# GitHub and tech-lead handoff

Status: local demo and submission files prepared. No repository, deployment, email or recording has been submitted externally.

- [ ] Use the newer email's 72-hour window from its receipt time (pack says 48 hours); Loom maximum is 8 minutes. Choose repository visibility.
- [ ] Read the updated stakeholder reply and unresolved business decisions.
- [ ] Follow the root README setup in a fresh environment.
- [ ] Install `requirements-dev.txt` and browser dependencies, then run `python -m pytest tests -q` — last full audit: 313 passing tests. See `docs/CASHIER_ACCEPTANCE.md` for Chrome/Chromium setup.
- [ ] Run `python exercise-pack/starter-kit/validate_seed.py` and `node --check app/static/app.js`.
- [ ] Review `FINAL_AUDIT.md` for verified results and limits.
- [ ] Launch with `run_demo.py` to keep the app and durable mock together.
- [ ] Commit application, scripts, tests, fixtures, docs, requirements, Dockerfile and CI.
- [ ] Exclude runtime credentials, databases, mock snapshots, logs, caches, screenshots, virtual environments and secrets.
- [ ] Review staged changes and `git diff --check` before committing.
- [ ] Create the repository in your account; if private, invite `kaustabh.ghosh@longivitate.in` and verify access.
- [ ] Optional showcase only: deploy one worker/container with a persistent `/data` volume behind HTTPS. Deployment is not required by the exercise.
- [ ] Configure a strong admin password as a hosting secret and verify the actual deployed URL.
- [ ] Share review credentials separately; never commit `runtime/demo-accounts.txt`.
- [ ] Record using `LOOM_SCRIPT.md` and `docs/DEMO_SCRIPT.md`.
- [ ] Cover the Must flow, 2–3 decisions, one decision to revisit, and where AI helped/misled you; keep the actual recording under 8 minutes.
- [ ] Replace submission-email placeholders with verified links before sending.

Reading order: README → stakeholder reply → acceptance map → architecture/source → tests/audit → deployment guide.
