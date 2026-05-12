# thinking.md — Part 3: Thinking Questions

**Scenario:** 3 AM. A guest at Villa B1 sends:  
*"There is no hot water and we have guests arriving for breakfast in 4 hours. This is unacceptable. I want a refund for tonight."*

---

## Question A — The Immediate Response

**The AI message sent at 3:04 AM:**

> Hi [Name], I'm really sorry — no hot water at 3 AM before your breakfast guests is completely unacceptable, and I understand why you're frustrated. I've flagged this as an emergency and our caretaker has been contacted right now. They will call you within 15 minutes. Our team will also review your refund request first thing in the morning — you will hear from us by 8 AM with a resolution. You have my word this will be sorted before your guests arrive.

**Why this wording:**  
The guest is stressed, sleep-deprived, and has a hard deadline. The message leads with validation (not apology-corporate-speak), gives a concrete next step with a specific time (15 minutes, not "soon"), commits to the refund conversation without promising it autonomously (which the AI should not do), and closes with a human guarantee. It never says "Hope this helps" or "Feel free to reach out."

---

## Question B — The System Design

Beyond sending the message, the platform should trigger a multi-layer response:

**Immediate (T+0 to T+5 min):**
1. **Classify as `complaint`** → `action = escalate` — the message is never auto-sent; a human reviews the draft before delivery (or it fires automatically with a human CC'd).
2. **Caretaker alert:** SMS + WhatsApp push to the caretaker on duty: *"URGENT — Villa B1, guest reporting no hot water. Guest has breakfast visitors at 7 AM. Call them immediately."*
3. **Duty manager alert:** Email + push notification to the on-call manager with full conversation context.
4. **Log to `property_issue_log`:** `issue_category = 'hot_water'`, linked to this message_id and property_id.
5. **Escalate conversation status** in the database: `conversations.status = 'escalated'`, `escalation_reason = 'complaint + 3am + time-sensitive'`.

**If no human responds in 30 minutes (T+30):**
1. **Escalation tier 2:** Alert the founder / senior operations contact via separate channel (e.g. phone call via Twilio).
2. **Follow-up message to guest:** *"We haven't forgotten you — our team is actively working on this. You will hear from us within 15 minutes."* (Keeps the guest from going to social media or review platforms in silence.)
3. **Log the 30-minute breach** in `ai_audit_log` as a process failure for post-incident review.

**Morning (T+5h):**
1. Duty manager reviews and closes the refund decision.
2. Resolution logged against the conversation; `property_issue_log.resolved_at` stamped.

---

## Question C — The Learning: Third Hot Water Complaint

**Pattern detection the system should already be doing:**  
A background job (cron, daily) queries:

```sql
SELECT COUNT(*) FROM property_issue_log
WHERE property_id = 'villa-b1'
  AND issue_category = 'hot_water'
  AND reported_at > NOW() - INTERVAL '60 days';
```

When this count hits **3**, the system automatically:

1. **Creates a maintenance task** in the operations system tagged RECURRING-ISSUE with full history attached. Not a chat message — an actual ticket.
2. **Emails the property manager** with the three complaint timestamps, guest names, and a flag: *"This issue has now occurred 3 times in 60 days. A plumber inspection is required before the next check-in."*
3. **Adds a pre-stay checklist item** to the villa B1 runbook: *"Water heater operational check — mandatory 24h before each check-in."* This checklist fires automatically on every future booking confirmation.
4. **Flags the issue in the booking confirmation flow:** If a new booking is confirmed before the maintenance ticket is resolved, the operations team gets an alert: *"Note: unresolved hot water issue at Villa B1."*

**What I would build to prevent complaint #4:**  
A lightweight **pre-stay operational check system** — 24 hours before each check-in, the caretaker receives a checklist (WhatsApp or app) covering known past failure points. They must tick off "water heater checked" before the green light is given. If the checklist isn't completed, the duty manager is alerted. This turns reactive complaint handling into proactive quality control — the complaint never reaches the guest because the problem is caught first.

The key insight: a guest messaging platform should not just handle communication — it should accumulate operational intelligence that prevents the next message from being a complaint at all.