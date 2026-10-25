# Deploying the review demo

This repository is ready for a Python/Docker host. It has not been pushed or deployed to a remote account. The Sites hosting runtime cannot directly run this Python/SQLite app, so the demo retains a conventional container deployment.

## Local verification

Run the README setup and tests first. Keep the UI/API and mock on the same machine; only expose the UI/API port. Default runner ports are 8000 and 8787. The local review instance uses 8001 and 8788 to preserve the earlier Swagger session.

## Container

Build with `docker build -t eluno-studio .`. Run one container with a persistent directory/volume mounted at `/data`. Configure these environment values in the hosting provider's secret manager:

| Setting | Purpose |
|---|---|
| `ELUNO_ADMIN_PASSWORD` | At least 12 characters; provisions `admin` on the first boot only |
| `ELUNO_RUNTIME=/data` | Persists both the application database and mock snapshot |
| `ELUNO_SECURE_COOKIES=1` | Required for an HTTPS deployment; already the Docker default |
| `PORT=8000` | Override only if your host assigns a different application port |

Example using an environment file kept outside Git:

```sh
docker run --name eluno-studio --env-file /secure/eluno-demo.env -p 8000:8000 -v eluno-data:/data eluno-studio
```

Put an HTTPS reverse proxy in front of port 8000. For a deliberately local HTTP container only, set `ELUNO_SECURE_COOKIES=0`; otherwise the browser correctly refuses to send Secure cookies over ordinary HTTP. Do not expose mock port 8787. Use exactly one worker/replica and a persistent disk; this SQLite/mock design does not support horizontally scaled or ephemeral serverless deployment.

The container runs as a non-root user. Make sure the mounted directory is writable by that user. Docker named volumes initialized from `/data` retain its ownership; arbitrary host bind mounts may need ownership adjustment.

## Accounts

Local setup generates accounts into the ignored `runtime/demo-accounts.txt`. Never commit that file or a populated runtime directory. Deployed instances should receive their administrator password through the host's secret manager; additional accounts can be provisioned with `scripts/manage_users.py` inside the container using `ELUNO_DB_PATH=/data/eluno.sqlite3`.

Password changes via the provisioning tool revoke existing sessions. Store staff accounts must map to a real seeded staff ID, e.g. HSR cashier `S105`, manager `S108`, optometrist `S107`. Central finance/admin accounts use store `*`. Use a private review URL or share credentials separately from the GitHub repository.

## Email delivery

Without SMTP, reports are fully generated and reviewable in **Report outbox**, but remain queued. To enable actual delivery configure:

```text
ELUNO_SMTP_HOST
ELUNO_SMTP_PORT=587
ELUNO_SMTP_USER
ELUNO_SMTP_PASSWORD
ELUNO_SMTP_FROM
ELUNO_FOUNDER_EMAIL
ELUNO_FINANCE_EMAIL
```

The SMTP path requires STARTTLS. The scheduler runs every 30 seconds, queues yesterday's report after 10:00 IST, and catches up when the app starts later. Keep the service running to send on schedule. Digest IDs prevent duplicate queue entries. An ambiguous delivery is marked `delivery_uncertain` and is not resent automatically. This needs operator review, not an unbounded retry loop.

## Backup and restart

Back up `eluno.sqlite3` and `mock-state.json` together with the app stopped, or use a coordinated backup mechanism. The wrapper snapshots mutations before acknowledging them. Do not delete/reset one side alone. The original exercise mock remains unchanged and still resets if launched directly; use `run_demo.py` for a durable demo.

## GitHub handoff

- Commit application code, tests, documentation, Dockerfile and `.github/workflows/tests.yml`.
- Exclude runtime databases, passwords, snapshots, logs, downloaded reference HTML and virtual environments.
- Run the acceptance suite and fixture validation before publishing.
- Put the review URL and a short demo recording in the GitHub description; share credentials privately.
- Do not describe the deployment as a production retail/payment system.

No hosting provider, repository remote or account was specified, so remote provisioning is intentionally not performed by the local runner.
