"""
api/models.py — Pydantic request/response schemas for LocalScript API.

Contract (from localscript-openapi.yaml, extended per Q&A checkpoint 1 & SSE update):
  POST /generate
  Request body : {"prompt": "<complete user input>", "context": "<rolling chat history>" (optional)}
  Response 200 : {"task_id": "<uuid>"}

  GET /status?task_id=<uuid>
  Response 200 : text/event-stream (SSE)
                 Example: data: {"stage": "generating", "message": "I am writing...", "code": "", "error": ""}

No business logic here — pure data shapes only.
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Incoming request: single text prompt + optional rolling context for multi-turn chats."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="The complete user input. All instructions must be sent in this single string (RU or EN).",
        examples=["Исправь этот код: \n```lua\nreturn 1\n```\nДобавь проверку на nil."],
    )
    context: str | None = Field(
        default=None,
        description="Conversation history (rolling context) for multi-turn chats (optional). Limit: 4096 chars.",
        examples=["User: как создать массив?\nAssistant: используй _utils.array.new()"],
    )


class TaskSubmitResponse(BaseModel):
    """Outgoing response for async submission: returns the tracking ID."""

    task_id: str = Field(
        ...,
        description="Unique identifier to subscribe to the SSE stream on /status?task_id=...",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class TaskStatusEvent(BaseModel):
    """
    Internal schema for SSE data payloads.
    Streamed as JSON strings: data: {"stage": "generating", "message": "Here is the code", "code": "...", "error": ""}
    """

    stage: str = Field(
        ...,
        description="Current pipeline stage: pending, generating, validating, retrying, done, error",
        examples=["validating"],
    )
    message: str = Field(
        default="",
        description="Natural language explanation, clarifying question, or conversational text from the LLM.",
        examples=["I found an error in your syntax. I fixed it by adding a check for nil."],
    )
    code: str = Field(
        default="",
        description="The generated Lua code.",
    )
    error: str = Field(
        default="",
        description="Error message if validation or generation failed.",
    )
