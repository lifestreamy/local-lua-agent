"""
api/models.py — Pydantic request/response schemas for LocalScript API.

Contract (from localscript-openapi.yaml):
  POST /generate
  Request body : {"prompt": "<natural language task>"}
  Response 200 : {"code": "<raw Lua string>"}

No business logic here — pure data shapes only.
"""

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Incoming request: natural language task description."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="Natural language description of the Lua task (RU or EN).",
        examples=["factorial(n), n >= 0"],
    )


class GenerateResponse(BaseModel):
    """Outgoing response: generated Lua code string."""

    code: str = Field(
        ...,
        description="Raw Lua code (no markdown fences). May be empty string on total failure.",
        examples=["function factorial(n)\n  if n <= 1 then return 1 end\n  return n * factorial(n - 1)\nend"],
    )
