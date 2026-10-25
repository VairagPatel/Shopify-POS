# Submission email — draft

**To:** Reply to the actual assignment thread.  
**Subject:** Eluno POS exercise — working demo and implementation

Hi team,

I've prepared Eluno Store Studio for review:

- **GitHub:** [ADD VERIFIED REPOSITORY URL]
- **Optional deployed demo:** [REMOVE THIS LINE IF NOT DEPLOYED; OTHERWISE ADD VERIFIED URL]
- **Walkthrough:** [ADD VERIFIED RECORDING URL]

The project includes an Eluno-branded working UI, authenticated roles, family billing with separate prescriptions, offers, inclusive GST, store invoices, full refunds and credit notes, lens-only remakes, cash reconciliation, channel/store reports and a scheduled-report outbox.

The repository includes the stakeholder reply, setup guide, acceptance checklist, architecture notes and automated tests. The last full suite passed 313 tests; a subsequent targeted Must-tier audit passed 35 tests. Chrome acceptance covers the sale/refund journey and family/remake/cash/clinical workflows. A separate Swagger-only check verifies direct login, source reads and quote preparation without opening the frontend.

Integration uses the supplied Shopify, store-tool and terminal mocks. The coverage view distinguishes implemented demo behavior from production dependencies: actual provider integration, business-policy sign-off, SMTP delivery and production performance/rollout validation. Review credentials will be shared separately.

I look forward to discussing the financial state machine, permissions, source reconciliation and the decisions needed before a store pilot.

Best regards,  
Vairag

Before sending: verify the links, reviewer access, current test result and actual deployed environment. This draft has not been sent.
