"""
api/models.py — Pydantic request/response schemas for LocalScript API.

Contract (from localscript-openapi.yaml, extended per Q&A checkpoint 1):
  POST /generate
  Request body : {"prompt": "<natural language task>", "context": "<existing Lua code>" (optional)}
  Response 200 : {"code": "<raw Lua string>"}

No business logic here — pure data shapes only.
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Incoming request: natural language task description + optional existing Lua code."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="Natural language description of the Lua task (RU or EN).",
        examples=["получить последний email из списка"],
    )
    context: str | None = Field(
        default=None,
        description=(
            "Existing Lua code to modify/extend (optional). "
            "If provided, the model will treat the prompt as a modification task. "
            "Omit this field entirely (or pass null) for fresh generation."
        ),
        examples=["local r = _utils.array.new()\nreturn r"],
    )


class GenerateResponse(BaseModel):
    """Outgoing response: generated Lua code string."""

    code: str = Field(
        ...,
        description="Raw Lua code (no markdown fences). May be empty string on total failure.",
        examples=["return wf.vars.emails[#wf.vars.emails]"],
    )