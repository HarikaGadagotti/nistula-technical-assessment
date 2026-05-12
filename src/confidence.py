from models import NormalisedMessage, QueryType, ActionType

_HIGH_CLARITY_TYPES = {
    QueryType.pre_sales_availability,
    QueryType.pre_sales_pricing,
    QueryType.post_sales_checkin,
}

_SPECIFICITY_MARKERS = [
    "18,000", "18000", "2,000", "2000",
    "april 20", "april 24",
    "2 pm", "2pm", "11 am", "11am",
    "nistula@2024", "7 days", "7-day",
    "caretaker", "chef", "assagao", "villa b1",
]


def _query_clarity_score(msg: NormalisedMessage) -> float:
    if msg.query_type in _HIGH_CLARITY_TYPES:
        return 1.0
    if msg.query_type == QueryType.special_request:
        return 0.75
    if msg.query_type == QueryType.general_enquiry:
        return 0.60
    return 0.50


def _reply_completeness_score(reply: str) -> float:
    hits = sum(1 for m in _SPECIFICITY_MARKERS if m in reply.lower())
    if hits >= 2:
        return 1.0
    if hits == 1:
        return 0.65
    return 0.25


def _message_complexity_score(msg: NormalisedMessage) -> float:
    q_count = msg.message_text.count("?")
    length = len(msg.message_text)
    if q_count <= 1 and length <= 60:
        return 1.0
    if q_count <= 2:
        return 0.80
    return 0.55


def _stop_reason_score(response) -> float:
    return 1.0 if getattr(response, "stop_reason", "end_turn") == "end_turn" else 0.50


def compute_confidence(msg: NormalisedMessage, reply: str, api_response) -> float:
    score = (
        0.30 * _query_clarity_score(msg)
        + 0.30 * _reply_completeness_score(reply)
        + 0.20 * _message_complexity_score(msg)
        + 0.20 * _stop_reason_score(api_response)
    )
    return max(0.0, min(1.0, score))


def get_action(confidence: float, query_type: QueryType) -> ActionType:
    if query_type == QueryType.complaint:
        return ActionType.escalate
    if confidence >= 0.85:
        return ActionType.auto_send
    if confidence >= 0.60:
        return ActionType.agent_review
    return ActionType.escalate