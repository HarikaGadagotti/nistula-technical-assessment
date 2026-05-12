import os
import time
import logging

from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import anthropic

from dotenv import load_dotenv

from models import InboundMessage, WebhookResponse
from normaliser import normalise_message
from prompt_builder import build_prompt
from confidence import compute_confidence, get_action


load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("nistula")


client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

MODEL = "claude-sonnet-4-20250514"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Nistula handler starting…")
    yield
    logger.info("Nistula handler stopped.")


app = FastAPI(
    title="Nistula Guest Message Handler",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "service": "Nistula Guest Message Handler",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/webhook/message", response_model=WebhookResponse)
async def handle_message(payload: InboundMessage):

    start_time = time.perf_counter()

    logger.info(
        "Inbound | source=%s | guest=%s",
        payload.source,
        payload.guest_name
    )

    normalised = normalise_message(payload)

    logger.info(
        "[%s] Normalised | query_type=%s",
        normalised.message_id,
        normalised.query_type.value
    )

    prompt = build_prompt(normalised)

    try:

        response = client.messages.create(
            model=MODEL,
            max_tokens=600,

            system=(
                "You are a warm, professional guest-relations assistant for Nistula, "
                "a luxury villa rental company in Goa, India. "

                "Only use information explicitly available in the provided property context. "

                "Do not invent operational teams, services, timelines, compensation amounts, "
                "or escalation steps that are not mentioned. "

                "If details are unavailable, say the operations team will confirm shortly. "

                "Reply concisely in a hospitality-style tone. "
                "Address the guest by first name. "

                "Prioritize empathy for complaints and clarity for operational questions."
            ),

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )

    except anthropic.AuthenticationError:
        raise HTTPException(
            status_code=500,
            detail="API key invalid."
        )

    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Rate limit reached."
        )

    except anthropic.APIError as e:
        logger.error("Anthropic error: %s", e)

        raise HTTPException(
            status_code=502,
            detail="AI service unavailable."
        )

    drafted_reply = response.content[0].text.strip()

    confidence = compute_confidence(
        normalised,
        drafted_reply,
        response
    )

    action = get_action(
        confidence,
        normalised.query_type
    )

    processing_time_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2
    )

    logger.info(
        "[%s] Completed | type=%s | score=%.2f | action=%s | latency=%.2fms",
        normalised.message_id,
        normalised.query_type.value,
        confidence,
        action.value,
        processing_time_ms,
    )

    return WebhookResponse(
        message_id=normalised.message_id,
        query_type=normalised.query_type,
        drafted_reply=drafted_reply,
        confidence_score=round(confidence, 4),
        action=action,
        processing_time_ms=processing_time_ms,
    )


@app.exception_handler(Exception)
async def global_error(request: Request, exc: Exception):

    logger.exception("Unhandled error: %s", exc)

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Something went wrong."
        }
    )