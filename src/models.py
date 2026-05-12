from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class MessageSource(str, Enum):
    whatsapp = "whatsapp"
    booking_com = "booking_com"
    airbnb = "airbnb"
    instagram = "instagram"
    direct = "direct"


class QueryType(str, Enum):
    pre_sales_availability = "pre_sales_availability"
    pre_sales_pricing = "pre_sales_pricing"
    post_sales_checkin = "post_sales_checkin"
    special_request = "special_request"
    complaint = "complaint"
    general_enquiry = "general_enquiry"


class ActionType(str, Enum):
    auto_send = "auto_send"
    agent_review = "agent_review"
    escalate = "escalate"


class InboundMessage(BaseModel):
    source: MessageSource
    guest_name: str = Field(..., min_length=1, max_length=120)
    message: str = Field(..., min_length=1, max_length=4000)
    timestamp: datetime
    booking_ref: Optional[str] = None
    property_id: Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "source": "whatsapp",
            "guest_name": "Rahul Sharma",
            "message": "Is the villa available from April 20 to 24? What is the rate for 2 adults?",
            "timestamp": "2026-05-05T10:30:00Z",
            "booking_ref": "NIS-2024-0891",
            "property_id": "villa-b1",
        }
    }}


class NormalisedMessage(BaseModel):
    message_id: str
    source: MessageSource
    guest_name: str
    message_text: str
    timestamp: datetime
    booking_ref: Optional[str]
    property_id: Optional[str]
    query_type: QueryType


class WebhookResponse(BaseModel):
    message_id: str
    query_type: QueryType
    drafted_reply: str
    confidence_score: float
    action: ActionType
    processing_time_ms: float