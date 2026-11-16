"""Industry Standard FastAPI Production Server for Financial Reconciliation Agent.
Provides Server-Sent Events (SSE) streaming for real-time lifecycle event monitoring,
REST endpoints for execution, human-in-the-loop resolutions, and skill file updates.
"""

import json
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.graph import build_financial_reconciliation_graph
from src.events import global_event_bus
from src.models import ReconciliationEvent
from src.skill_store import SkillStore
from data.sample_data import get_sample_reconciliation_payload

app = FastAPI(
    title="Financial Reconciliation Multi-Agent System (LangGraph + FastAPI)",
    description="Enterprise LangGraph agent reconciling third-party audit reports against Google Drive bills with real-time event streaming.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for active run state and SSE client queues
run_history: Dict[str, Any] = {}


class HumanDecisionRequest(BaseModel):
    review_id: str
    action: str  # "APPROVE_MATCH" or "REJECT_ANOMALY"
    notes: Optional[str] = "Approved by human auditor via API"


class SkillRuleRequest(BaseModel):
    rule_id: str
    description: str
    action: str


@app.get("/")
def root():
    return {
        "system": "Financial Reconciliation Agent",
        "frameworks": ["LangGraph 0.2+", "FastAPI", "Pydantic v2", "Docling"],
        "endpoints": {
            "stream_events": "GET /api/reconcile/stream",
            "run_reconciliation": "POST /api/reconcile/run",
            "resolve_review": "POST /api/review/resolve",
            "get_skill_file": "GET /api/skill-file"
        }
    }


@app.get("/api/reconcile/stream")
async def stream_reconciliation():
    """Server-Sent Events (SSE) endpoint: runs the LangGraph agent and streams
    live events (ingestion, extraction, deduplication, LLM reasoning, review) in real time.
    """
    event_queue: asyncio.Queue = asyncio.Queue()

    def sse_event_listener(event: ReconciliationEvent):
        try:
            event_queue.put_nowait(event)
        except Exception:
            pass

    global_event_bus.register_listener(sse_event_listener)

    async def event_generator():
        # Launch graph execution in background task
        graph = build_financial_reconciliation_graph()
        initial_state = get_sample_reconciliation_payload()

        async def run_graph():
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, graph.invoke, initial_state, {"configurable": {"thread_id": "stream_run"}})

        task = asyncio.create_task(run_graph())

        while not task.done() or not event_queue.empty():
            try:
                event: ReconciliationEvent = await asyncio.wait_for(event_queue.get(), timeout=0.3)
                payload = {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "stage": event.stage,
                    "message": event.message,
                    "data": event.data,
                    "timestamp": event.timestamp
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

        result = await task
        run_history[initial_state["run_id"]] = result
        completion_msg = {
            "event_type": "PIPELINE_COMPLETE",
            "summary": result.get("summary", {}),
            "final_report": result.get("final_report", "")
        }
        yield f"data: {json.dumps(completion_msg)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/reconcile/run")
def execute_reconciliation(custom_payload: Optional[Dict[str, Any]] = None):
    """Executes reconciliation synchronously and returns full result JSON."""
    graph = build_financial_reconciliation_graph()
    payload = custom_payload if custom_payload else get_sample_reconciliation_payload()
    result = graph.invoke(payload, {"configurable": {"thread_id": payload.get("run_id", "prod_thread")}})
    run_history[payload.get("run_id", "default")] = result

    return {
        "status": "success",
        "summary": result.get("summary", {}),
        "f1_metrics": result.get("f1_metrics", {}),
        "discrepancies": result.get("discrepancies", []),
        "matches": [m.dict() if hasattr(m, 'dict') else m for m in result.get("matches", [])],
        "final_report": result.get("final_report", "")
    }


@app.get("/api/runs/{run_id}")
def get_run_details(run_id: str):
    if run_id not in run_history:
        raise HTTPException(status_code=404, detail="Run ID not found")
    res = run_history[run_id]
    return {
        "run_id": run_id,
        "summary": res.get("summary", {}),
        "f1_metrics": res.get("f1_metrics", {}),
        "report": res.get("final_report", "")
    }


@app.get("/api/skill-file")
def get_skill_rules():
    """Returns current active versioned skill rules and aliases."""
    store = SkillStore()
    return store.data


@app.post("/api/skill-file/rule")
def add_skill_rule(req: SkillRuleRequest):
    """Adds a learned domain rule into the persistent skill file."""
    store = SkillStore()
    store.append_rule(req.rule_id, req.description, req.action)
    return {"status": "success", "message": f"Rule {req.rule_id} appended and persisted."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
