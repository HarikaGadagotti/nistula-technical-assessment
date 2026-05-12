import uuid
from models import InboundMessage, NormalisedMessage
from classifier import classify_query


def normalise_message(payload: InboundMessage) -> NormalisedMessage:
    cleaned_text = payload.message.strip()

    return NormalisedMessage(
        message_id=str(uuid.uuid4()),
        source=payload.source,
        guest_name=payload.guest_name.strip().title(),
        message_text=cleaned_text,
        timestamp=payload.timestamp,
        booking_ref=payload.booking_ref,
        property_id=payload.property_id,
        query_type=classify_query(cleaned_text),
    )