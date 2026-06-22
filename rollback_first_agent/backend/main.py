from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - import guard for minimal envs
    raise RuntimeError(
        "FastAPI backend requires dependencies from requirements.txt"
    ) from exc

from rollback_first_agent.core import RollbackFirstAgent, SQLiteActionStore


DB_PATH = Path(__file__).resolve().parents[2] / "rollback_first_agent.sqlite3"
store = SQLiteActionStore(DB_PATH)
store.seed_demo_data()
agent = RollbackFirstAgent(store)

app = FastAPI(title="Rollback-First Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CommandRequest(BaseModel):
    message: str


class ExecuteRequest(BaseModel):
    user_request: str
    original_action: dict[str, Any] | None = None
    planned_action: dict[str, Any] | None = None
    final_action: dict[str, Any] | None = None
    rollback_plan: dict[str, Any]
    gate_result: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/plan")
def plan_command(request: CommandRequest) -> dict[str, Any]:
    try:
        return agent.plan(request.message).to_dict()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/agent/execute")
def execute_plan(request: ExecuteRequest) -> dict[str, Any]:
    try:
        from rollback_first_agent.core import (
            ActionType,
            AgentPlan,
            GateDecision,
            GateResult,
            PlannedAction,
            RecoveryLevel,
            RollbackPlan,
            RollbackType,
        )

        original_payload = request.original_action or request.planned_action
        final_payload = request.final_action or request.planned_action
        if original_payload is None or final_payload is None:
            raise ValueError("original_action/final_action is required")
        original_action = PlannedAction(
            action_type=ActionType(original_payload["action_type"]),
            arguments=original_payload["arguments"],
            description=original_payload["description"],
        )
        final_action = PlannedAction(
            action_type=ActionType(final_payload["action_type"]),
            arguments=final_payload["arguments"],
            description=final_payload["description"],
        )
        safe_payload = (request.gate_result or {}).get("safe_alternative")
        safe_alternative = (
            PlannedAction(
                action_type=ActionType(safe_payload["action_type"]),
                arguments=safe_payload["arguments"],
                description=safe_payload["description"],
            )
            if safe_payload
            else None
        )
        gate_result = GateResult(
            gate_decision=GateDecision(
                (request.gate_result or {}).get("gate_decision", "execute")
            ),
            reason=(request.gate_result or {}).get(
                "reason", "이 작업은 완전히 복구 가능하므로 자동 실행할 수 있습니다."
            ),
            safe_alternative=safe_alternative,
        )
        rollback_plan = RollbackPlan(
            rollback_type=RollbackType(request.rollback_plan["rollback_type"]),
            rollback_arguments=request.rollback_plan["rollback_arguments"],
            rollback_available=bool(request.rollback_plan["rollback_available"]),
            recovery_level=RecoveryLevel(
                request.rollback_plan.get("recovery_level", "fully_reversible")
            ),
            reason=request.rollback_plan["reason"],
        )
        plan = AgentPlan(
            request.user_request,
            original_action,
            rollback_plan,
            gate_result,
            final_action,
        )
        return agent.execute(plan)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/agent/run")
def run_command(request: CommandRequest) -> dict[str, Any]:
    try:
        return agent.run(request.message)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/agent/actions/{action_id}/rollback")
def rollback_action(action_id: int) -> dict[str, Any]:
    try:
        return agent.rollback(action_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/agent/history")
def history() -> list[dict[str, Any]]:
    return store.fetch_action_logs()


@app.get("/todos")
def todos() -> list[dict[str, Any]]:
    return store.fetch_todos()


@app.get("/schedules")
def schedules() -> list[dict[str, Any]]:
    return store.fetch_schedules()


@app.get("/notices")
def notices() -> list[dict[str, Any]]:
    return store.fetch_notices()
