from models import NormalisedMessage, QueryType

PROPERTY_CONTEXT = """
PROPERTY CONTEXT — use only this, do not invent details:
──────────────────────────────────────────────────────────
Property    : Villa B1, Assagao, North Goa
Bedrooms    : 3  |  Max guests: 6  |  Private pool: Yes
Check-in    : 2 PM   |  Check-out: 11 AM
Base rate   : INR 18,000 per night (up to 4 guests)
Extra guest : INR 2,000 per night per person
WiFi        : Nistula@2024
Caretaker   : Available 8 AM – 10 PM
Chef on call: Yes (24-hour pre-booking required)
April 20–24 : Available
Cancellation: Free up to 7 days before check-in
──────────────────────────────────────────────────────────
"""

QUERY_GUIDANCE = {
    QueryType.pre_sales_availability: (
        "Confirm availability for the dates mentioned, quote the nightly rate, "
        "calculate the total if dates are clear, and invite them to book."
    ),
    QueryType.pre_sales_pricing: (
        "Give a clear rate breakdown — nightly base, extra guest charges if relevant — "
        "and invite them to confirm dates."
    ),
    QueryType.post_sales_checkin: (
        "Answer directly from the property context. Give the check-in time, "
        "WiFi password, or any access detail the guest asked about."
    ),
    QueryType.special_request: (
        "Acknowledge the request warmly. Confirm what is possible from the context "
        "and note anything the team will follow up on."
    ),
    QueryType.complaint: (
        "Open with genuine empathy — no corporate phrases. State the immediate action "
        "being taken right now. Do not promise a refund without manager sign-off. "
        "Give a specific callback or resolution time."
    ),
    QueryType.general_enquiry: (
        "Answer using only the property context. If the answer isn't in the context, "
        "say the team will confirm shortly rather than guessing."
    ),
}


def build_prompt(msg: NormalisedMessage) -> str:
    guidance = QUERY_GUIDANCE.get(msg.query_type, QUERY_GUIDANCE[QueryType.general_enquiry])
    booking_line = (
        f"Booking reference: {msg.booking_ref}" if msg.booking_ref
        else "No booking reference — likely a new enquiry."
    )

    return f"""
{PROPERTY_CONTEXT}

GUEST DETAILS
Name    : {msg.guest_name}
Channel : {msg.source.value}
{booking_line}
Sent at : {msg.timestamp.isoformat()}

GUEST MESSAGE
\"\"\"{msg.message_text}\"\"\"

CLASSIFICATION: {msg.query_type.value}

TASK
{guidance}

Write the reply to {msg.guest_name.split()[0]} now.
Keep it under 120 words. Be warm, specific, and direct.
Do not mirror the guest message back unnecessarily.
Avoid generic filler phrases like "Hope this helps!" or "Please don't hesitate to reach out."
""".strip()