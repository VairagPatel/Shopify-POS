# Final submission email — DRAFT ONLY

**To:** Reply to the original Eluno assignment email thread (don't invent or guess recipient addresses)

**Subject:** Re: Eluno POS exercise

Hi Kaustabh and team,

Thank you for sharing the exercise. I've completed my Eluno POS submission and included both links below:

**GitHub repository:** [ADD VERIFIED REPO URL]
  
**Loom walkthrough (under 8 minutes):** [ADD VERIFIED LOOM URL]

The repository includes `STAKEHOLDER_REPLY.md`, the FastAPI application, automated tests, a setup guide in `README.md`, and `DECISIONS.md` explaining the engineering choices and trade-offs.

The implementation covers a mock-backed sale flow with prescription checks, data-driven offers, inclusive GST, payment and Shopify order creation, multi-pair checkout for one customer, full refunds with frame-only restocking, and Shopify-sourced day-end reporting. The current test suite has **35 passing tests**.

I've also documented the boundaries of this exercise build, including manual reconciliation for uncertain terminal outcomes, repeated-SKU and mixed-person family-cart limitations, and reporting differences between order dates and refund settlement dates. The README also notes that launching the mock and application currently takes two processes.

I look forward to walking you through the architecture, the decisions, and what I'd prioritize for a production rollout.

Best regards,  
Vairag Akbari

---

**Before sending:** Replace the bracketed URLs with working links, confirm repo permissions and Loom visibility, verify test count and current scope, and resolve or explicitly leave the one-command startup gap. **Do not send without final approval.**
