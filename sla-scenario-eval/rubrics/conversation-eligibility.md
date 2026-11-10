# Conversation Eligibility for SLA Scenario Coverage (helper)

**Judge template:** `pointwise`

## What's being measured

Whether a conversation belongs in the denominator when scoring Conversation Coverage for SLA scenarios. SLA ships scenarios that drive **tool-call-based resolutions** — i.e. the agent completes a backend action on behalf of the customer. Conversations that don't fit that shape over-penalize the scenario set when counted against coverage.

A conversation is **sla_eligible** if BOTH:

1. **Fully resolved in-session** — the customer's primary request was completed before the conversation ended. Not escalated, not "we'll follow up", not dropped mid-screen-share, not routed to another team. The fix / data / completion happened in-session.
2. **Required a backend action, not pure knowledge lookup** — the agent did something a tool call would represent: changed configuration, corrected data, created a record, updated a field, ran a job, applied a permission. Convos where the agent just *answered a question* ("the default group number is X", "that feature isn't supported, use workaround Y") or *walked the customer through self-service clicks* ("click Settings, then Commit") are knowledge-lookup / how-to guidance — not SLA-shaped.

Everything else is **ineligible**:

- `UNRESOLVED` — chat dropped, timed out mid-troubleshoot, escalated to Tier 2 / engineering with no in-session fix, "we'll get back to you via email"
- `PARTIALLY_RESOLVED` — partial fulfillment, workaround only, case created but underlying issue not fixed
- `NOT_ACTIONABLE` — voicemail, dead air, agent-side test recording, wrong-number / out-of-scope / unintelligible
- `KNOWLEDGE_ONLY` — fully resolved but the "resolution" is an answer, explanation, or step-by-step guidance (no backend mutation)

## Decision order

1. Is there any actionable in-scope customer request? If no → `NOT_ACTIONABLE`.
2. Did the agent complete the request in-session? If no → `UNRESOLVED` or `PARTIALLY_RESOLVED`.
3. Did completion require a backend action (configure, correct, create, update, apply, run)? If no → `KNOWLEDGE_ONLY`.
4. Otherwise → `sla_eligible`.

## Reading the transcript — common pitfalls

- **The last turn is often a system/auto-timeout line, not the agent giving up.** Transcripts frequently end with `"Looks like you may have stepped away for a moment. Please note this chat session will end in [DATE]."` or similar auto-generated messages. These are session-end boilerplate — they do NOT invalidate a resolution that occurred earlier in the transcript. If the customer confirmed the fix worked before the auto-timeout, the convo IS resolved.
- **Customer confirmation is the resolution signal, not the final turn.** Look for the customer saying "it works now", "they all show up", "that fixed it", "thanks that worked", etc. If that signal is present and the agent-side action preceded it, the convo is RESOLVED — regardless of whether the agent closed with pleasantries or the session timed out afterward.
- **Agent-side first-person backend actions are tool calls, even without a UI shown.** When the agent says "let me take a look and see if I can correct that on my end" / "I was able to get it corrected on my end" / "I've gone ahead and updated it" / "I pushed that through", those are backend actions (BACKEND_ACTION), not knowledge-lookup. Pair with a customer confirmation to classify as `sla_eligible`.
- **"Click here, then click there" is KNOWLEDGE_ONLY even if the customer confirms it worked.** The *customer* did the backend action; the agent only provided guidance. SLA scenarios automate agent-side actions, not customer-side click-throughs.

## Output

Return STRICT JSON:

```json
{
  "score": "sla_eligible" | "ineligible",
  "resolution": "RESOLVED" | "PARTIALLY_RESOLVED" | "UNRESOLVED" | "NOT_ACTIONABLE",
  "action_type": "BACKEND_ACTION" | "KNOWLEDGE_ONLY" | "NONE",
  "reason": "<one-line>"
}
```

## Anchors

### sla_eligible — Retail backend fix

Conversation: Customer says their order was double-charged. Agent verifies the duplicate charge in the system, refunds one of the charges, confirms refund processed. Customer thanks and leaves satisfied.
Output: `{"score": "sla_eligible", "resolution": "RESOLVED", "action_type": "BACKEND_ACTION", "reason": "agent processed refund via system — backend action, fully resolved"}`

### sla_eligible — EdTech backend config fix (auto-timeout at end)

Conversation: Customer reports missing Manage Columns options in Performance Matters. Agent: "Let me take a look and see if I can correct that on my end for you." Agent then: "I believe I was able to get it corrected on my end. Please refresh the page and see if the expected options show up now." Customer: "they all show up now! thank you". Agent: "Perfect! I am happy to help!" Then: `"Looks like you may have stepped away for a moment. Please note this chat session will end in [DATE]."` (auto-generated session-timeout line).
Output: `{"score": "sla_eligible", "resolution": "RESOLVED", "action_type": "BACKEND_ACTION", "reason": "agent corrected the configuration server-side; customer confirmed fix worked before auto-timeout"}`
Note: the auto-timeout line is boilerplate, NOT a sign of unresolved state. The resolution signal is the customer's "they all show up now!" confirmation.

### ineligible — knowledge lookup

Conversation: Admin asks "what's the default security group number for new users?". Agent answers "it's 7". Customer confirms and leaves.
Output: `{"score": "ineligible", "resolution": "RESOLVED", "action_type": "KNOWLEDGE_ONLY", "reason": "agent answered a lookup question — no backend mutation"}`

### ineligible — how-to walkthrough

Conversation: Customer asks how to commit their schedule. Agent walks them through clicking Setup → Commit → Confirm. Customer confirms it worked.
Output: `{"score": "ineligible", "resolution": "RESOLVED", "action_type": "KNOWLEDGE_ONLY", "reason": "agent gave click-through guidance — customer performed the action, not the agent"}`

### ineligible — escalation

Conversation: Customer reports a bug in Applicant Tracking. Agent says "I'll create a case for engineering, they'll follow up via email." Chat ends.
Output: `{"score": "ineligible", "resolution": "UNRESOLVED", "action_type": "NONE", "reason": "escalated to engineering, no in-session fix"}`

### ineligible — dropped chat

Conversation: Agent greets, asks for screen share link, customer accepts, chat times out before troubleshooting starts.
Output: `{"score": "ineligible", "resolution": "UNRESOLVED", "action_type": "NONE", "reason": "chat timed out before resolution"}`

### ineligible — voicemail / test

Conversation: Agent speaks a single-turn test message to confirm recording works. No customer.
Output: `{"score": "ineligible", "resolution": "NOT_ACTIONABLE", "action_type": "NONE", "reason": "agent-side test, no customer interaction"}`
