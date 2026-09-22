"""FastAPI service: exact tensor-network contraction optimizer."""

from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .optimizer import optimize
from .validation import validate_network

app = FastAPI(
    title="Tensor Network Contraction Planner",
    version="1.0.0",
    description="精确枚举收缩树：先最小化峰值内存，再最小化总乘法数。",
)

# The frontend talks to the API through its own reverse proxy in production;
# allowing CORS as well keeps local `vite dev` workflows working.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "api"}


@app.get("/api/info")
def info() -> dict:
    return {
        "limits": {
            "tensors": [2, 11],
            "indices_per_tensor": [1, 6],
            "dimension": [2, 1000],
            "index_occurrences": [1, 2],
        },
        "cost_model": {
            "merge_multiplications": "product(dim(i) for i in boundary_union)",
            "result_size": "product(dim(i) for i in symmetric_difference)",
            "peak": "max over inputs and intermediates",
        },
        "optimization_priority": [
            "peak_memory",
            "total_multiplications",
            "canonical_tree",
        ],
    }


@app.post("/api/contract")
async def contract(request: Request) -> JSONResponse:
    """Validate and optimize.  Bad input never raises: it returns ok=false
    with a located error list so the client can preserve what was typed."""
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return JSONResponse(
            {
                "ok": False,
                "errors": [
                    {
                        "code": "invalid_json",
                        "loc": "",
                        "message": f"请求体不是合法 JSON：{exc.msg}（位置 {exc.pos}）。",
                    }
                ],
            }
        )

    leaves, dims, errors = validate_network(payload)
    if errors:
        return JSONResponse({"ok": False, "errors": errors})
    result = optimize(leaves, dims)
    result["ok"] = True
    return JSONResponse(result)
