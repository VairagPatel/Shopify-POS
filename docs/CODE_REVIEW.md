# Readability and implementation review

The project-owned application, tests and launch scripts were reviewed and formatted. The original exercise pack remains unmodified.

- Every named Python function has a preceding purpose comment; core functions additionally have editor-visible docstrings. Browser functions have JSDoc purpose comments.
- Selected ambiguous legacy names were expanded, including SQLite connections/cursors, checkout identifiers, payment references, frame/lens indices and refund identifiers. Short mathematical loop variables remain where their meaning is local and clear.
- Monetary operations use integer paise and decimal strings at the integration boundary. UI formatting does not determine charged totals.
- Financial mutations preserve compare-and-set state transitions and do not automatically retry an unknown external result.
- Authentication applies to both the original endpoints and the new UI APIs. Server roles/store scope and CSRF checks do not rely on hidden frontend controls.
- Drawer calculation uses a baseline of source transaction IDs, avoiding same-second timestamp errors between local microseconds and mock timestamps.
- The single-worker mutation lock prevents a drawer close racing another app request that changes cash. This is deliberately a single-instance demo, not distributed coordination.
- New schema changes are additive. The original session database and supplied mock code are not reset or rewritten.
- Browser-rendered data is escaped, authenticated sessions are HttpOnly, and no default deployment password is embedded in source.
- Daily reports and cash alerts have durable outbox status; uncertain SMTP outcomes require review rather than duplicate-prone automatic resend.

Limitations explicitly retained: production auth lifecycle/SSO and security review; unknown terminal recovery; live pagination/reservation/settlement; legally approved invoice fields; multi-worker operation; configured offer-policy sign-off. These are documented boundaries, not hidden behind success labels.

The historical `DECISIONS.md` captures the API-first exercise stages. Current UI/expanded-scope decisions are described here and in the root README.
