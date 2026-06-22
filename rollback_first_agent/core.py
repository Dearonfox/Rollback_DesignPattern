from __future__ import annotations

import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class ActionType(str, Enum):
    CREATE_TODO = "create_todo"
    UPDATE_TODO = "update_todo"
    DELETE_TODO = "delete_todo"
    CREATE_SCHEDULE = "create_schedule"
    UPDATE_SCHEDULE = "update_schedule"
    DELETE_SCHEDULE = "delete_schedule"
    SEND_NOTICE = "send_notice"
    CREATE_NOTICE_DRAFT = "create_notice_draft"


class RollbackType(str, Enum):
    DELETE_CREATED_TODO = "delete_created_todo"
    RESTORE_UPDATED_TODO = "restore_updated_todo"
    RESTORE_DELETED_TODO = "restore_deleted_todo"
    DELETE_CREATED_SCHEDULE = "delete_created_schedule"
    RESTORE_UPDATED_SCHEDULE = "restore_updated_schedule"
    RESTORE_DELETED_SCHEDULE = "restore_deleted_schedule"
    DELETE_NOTICE_DRAFT = "delete_notice_draft"
    NOT_AVAILABLE = "not_available"


class RecoveryLevel(str, Enum):
    FULLY_REVERSIBLE = "fully_reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class GateDecision(str, Enum):
    EXECUTE = "execute"
    APPROVAL_REQUIRED = "approval_required"
    TRANSFORM_TO_SAFE_ACTION = "transform_to_safe_action"


class ActionStatus(str, Enum):
    PLANNED = "planned"
    EXECUTED = "executed"
    TRANSFORMED = "transformed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class PlannedAction:
    action_type: ActionType
    arguments: dict[str, Any]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "arguments": self.arguments,
            "description": self.description,
        }


@dataclass(frozen=True)
class RollbackPlan:
    rollback_type: RollbackType
    rollback_arguments: dict[str, Any]
    rollback_available: bool
    recovery_level: RecoveryLevel
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_type": self.rollback_type.value,
            "rollback_arguments": self.rollback_arguments,
            "rollback_available": self.rollback_available,
            "recovery_level": self.recovery_level.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class GateResult:
    gate_decision: GateDecision
    reason: str
    safe_alternative: PlannedAction | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_decision": self.gate_decision.value,
            "reason": self.reason,
            "safe_alternative": self.safe_alternative.to_dict()
            if self.safe_alternative
            else None,
        }


@dataclass(frozen=True)
class AgentPlan:
    user_request: str
    original_action: PlannedAction
    rollback_plan: RollbackPlan
    gate_result: GateResult
    final_action: PlannedAction

    @property
    def planned_action(self) -> PlannedAction:
        return self.final_action

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_request": self.user_request,
            "original_action": self.original_action.to_dict(),
            "planned_action": self.final_action.to_dict(),
            "rollback_plan": self.rollback_plan.to_dict(),
            "gate_result": self.gate_result.to_dict(),
            "final_action": self.final_action.to_dict(),
        }


class SQLiteActionStore:
    """SQLite store for todos, schedules, and action ledger."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.initialize()

    def initialize(self) -> None:
        with self.lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT DEFAULT 'open',
                    deadline TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

            CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

                CREATE TABLE IF NOT EXISTS notices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    sent_at TEXT
                );

                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_request TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_payload TEXT NOT NULL,
                    original_action_type TEXT,
                    original_action_payload TEXT,
                    final_action_type TEXT,
                    final_action_payload TEXT,
                    rollback_type TEXT NOT NULL,
                    rollback_payload TEXT NOT NULL,
                    rollback_available INTEGER NOT NULL,
                    recovery_level TEXT,
                    gate_decision TEXT,
                    safe_alternative TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    executed_at TEXT,
                    rolled_back_at TEXT
                );
                """
            )
            self._migrate_action_logs()
            self.conn.commit()

    def _migrate_action_logs(self) -> None:
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(action_logs)").fetchall()
        }
        migrations = {
            "original_action_type": "TEXT",
            "original_action_payload": "TEXT",
            "final_action_type": "TEXT",
            "final_action_payload": "TEXT",
            "recovery_level": "TEXT",
            "gate_decision": "TEXT",
            "safe_alternative": "TEXT",
        }
        for column, column_type in migrations.items():
            if column not in existing:
                self.conn.execute(
                    f"ALTER TABLE action_logs ADD COLUMN {column} {column_type}"
                )

    def seed_demo_data(self) -> None:
        if self.fetch_todos():
            return
        self.create_todo("AI 과제 주제 정리", status="done")
        self.create_todo("운영체제 ch10 복습", status="done")
        self.create_todo("팀플 회의록 작성", status="done")
        self.create_todo("논문 초안 다듬기", status="open")
        self.create_schedule(
            title="운영체제 공부",
            start_time="2026-06-22 15:00",
            end_time="2026-06-22 16:00",
        )

    def create_todo(
        self,
        title: str,
        description: str = "",
        status: str = "open",
        deadline: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        cursor = self.conn.execute(
            """
            INSERT INTO todos (title, description, status, deadline, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, status, deadline, now, now),
        )
        self.conn.commit()
        return self.get_todo(cursor.lastrowid)

    def update_todo(self, todo_id: int, **updates: Any) -> dict[str, Any]:
        current = self.get_todo(todo_id)
        if not current:
            raise ValueError(f"todo not found: {todo_id}")
        fields = {key: value for key, value in updates.items() if value is not None}
        fields["updated_at"] = self._now()
        assignments = ", ".join(f"{key}=?" for key in fields)
        self.conn.execute(
            f"UPDATE todos SET {assignments} WHERE id=?",
            (*fields.values(), todo_id),
        )
        self.conn.commit()
        return self.get_todo(todo_id)

    def delete_todos(self, todo_ids: list[int]) -> list[dict[str, Any]]:
        backup = [self.get_todo(todo_id) for todo_id in todo_ids]
        backup = [item for item in backup if item]
        if backup:
            placeholders = ",".join("?" for _ in backup)
            self.conn.execute(
                f"DELETE FROM todos WHERE id IN ({placeholders})",
                [item["id"] for item in backup],
            )
            self.conn.commit()
        return backup

    def restore_todos(self, todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        restored = []
        for todo in todos:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO todos
                (id, title, description, status, deadline, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    todo["id"],
                    todo["title"],
                    todo.get("description", ""),
                    todo.get("status", "open"),
                    todo.get("deadline"),
                    todo.get("created_at", self._now()),
                    self._now(),
                ),
            )
            restored.append(self.get_todo(todo["id"]) or todo)
        self.conn.commit()
        return restored

    def get_todo(self, todo_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        return dict(row) if row else None

    def fetch_todos(self, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM todos WHERE status=? ORDER BY id", (status,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM todos ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def create_schedule(
        self,
        title: str,
        start_time: str,
        end_time: str,
        description: str = "",
    ) -> dict[str, Any]:
        now = self._now()
        cursor = self.conn.execute(
            """
            INSERT INTO schedules (title, description, start_time, end_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, description, start_time, end_time, now, now),
        )
        self.conn.commit()
        return self.get_schedule(cursor.lastrowid)

    def update_schedule(self, schedule_id: int, **updates: Any) -> dict[str, Any]:
        current = self.get_schedule(schedule_id)
        if not current:
            raise ValueError(f"schedule not found: {schedule_id}")
        fields = {key: value for key, value in updates.items() if value is not None}
        fields["updated_at"] = self._now()
        assignments = ", ".join(f"{key}=?" for key in fields)
        self.conn.execute(
            f"UPDATE schedules SET {assignments} WHERE id=?",
            (*fields.values(), schedule_id),
        )
        self.conn.commit()
        return self.get_schedule(schedule_id)

    def delete_schedules(self, schedule_ids: list[int]) -> list[dict[str, Any]]:
        backup = [self.get_schedule(schedule_id) for schedule_id in schedule_ids]
        backup = [item for item in backup if item]
        if backup:
            placeholders = ",".join("?" for _ in backup)
            self.conn.execute(
                f"DELETE FROM schedules WHERE id IN ({placeholders})",
                [item["id"] for item in backup],
            )
            self.conn.commit()
        return backup

    def restore_schedules(self, schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
        restored = []
        for schedule in schedules:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO schedules
                (id, title, description, start_time, end_time, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    schedule["id"],
                    schedule["title"],
                    schedule.get("description", ""),
                    schedule["start_time"],
                    schedule["end_time"],
                    schedule.get("created_at", self._now()),
                    self._now(),
                ),
            )
            restored.append(self.get_schedule(schedule["id"]) or schedule)
        self.conn.commit()
        return restored

    def get_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM schedules WHERE id=?", (schedule_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_schedule_by_title(self, title_hint: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM schedules WHERE title LIKE ? ORDER BY id LIMIT 1",
            (f"%{title_hint}%",),
        ).fetchone()
        return dict(row) if row else None

    def fetch_schedules(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM schedules ORDER BY start_time").fetchall()
        return [dict(row) for row in rows]

    def create_notice_draft(
        self,
        target: str,
        title: str,
        content: str,
    ) -> dict[str, Any]:
        now = self._now()
        cursor = self.conn.execute(
            """
            INSERT INTO notices (target, title, content, status, created_at, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (target, title, content, "draft", now, None),
        )
        self.conn.commit()
        return self.get_notice(cursor.lastrowid)

    def delete_notices(self, notice_ids: list[int]) -> list[dict[str, Any]]:
        backup = [self.get_notice(notice_id) for notice_id in notice_ids]
        backup = [item for item in backup if item]
        if backup:
            placeholders = ",".join("?" for _ in backup)
            self.conn.execute(
                f"DELETE FROM notices WHERE id IN ({placeholders})",
                [item["id"] for item in backup],
            )
            self.conn.commit()
        return backup

    def get_notice(self, notice_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM notices WHERE id=?", (notice_id,)).fetchone()
        return dict(row) if row else None

    def fetch_notices(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM notices ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def create_action_log(
        self,
        user_request: str,
        original_action: PlannedAction,
        final_action: PlannedAction,
        rollback: RollbackPlan,
        gate_result: GateResult,
        status: ActionStatus,
    ) -> int:
        now = self._now()
        cursor = self.conn.execute(
            """
            INSERT INTO action_logs
            (user_request, action_type, action_payload,
             original_action_type, original_action_payload,
             final_action_type, final_action_payload,
             rollback_type, rollback_payload, rollback_available,
             recovery_level, gate_decision, safe_alternative,
             status, created_at, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_request,
                final_action.action_type.value,
                json.dumps(final_action.to_dict(), ensure_ascii=False),
                original_action.action_type.value,
                json.dumps(original_action.to_dict(), ensure_ascii=False),
                final_action.action_type.value,
                json.dumps(final_action.to_dict(), ensure_ascii=False),
                rollback.rollback_type.value,
                json.dumps(rollback.to_dict(), ensure_ascii=False),
                int(rollback.rollback_available),
                rollback.recovery_level.value,
                gate_result.gate_decision.value,
                json.dumps(gate_result.safe_alternative.to_dict(), ensure_ascii=False)
                if gate_result.safe_alternative
                else None,
                status.value,
                now,
                now if status in {ActionStatus.EXECUTED, ActionStatus.TRANSFORMED} else None,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def get_action_log(self, action_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM action_logs WHERE id=?", (action_id,)
        ).fetchone()
        return dict(row) if row else None

    def fetch_action_logs(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM action_logs ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def mark_rolled_back(self, action_id: int) -> None:
        self.conn.execute(
            "UPDATE action_logs SET status=?, rolled_back_at=? WHERE id=?",
            (ActionStatus.ROLLED_BACK.value, self._now(), action_id),
        )
        self.conn.commit()

    def _now(self) -> str:
        return datetime.now().replace(microsecond=0).isoformat(sep=" ")


class RollbackFirstAgent:
    """Agent workflow: Analyze -> Plan -> Prepare Rollback -> Execute -> Record."""

    def __init__(self, store: SQLiteActionStore | None = None):
        self.store = store or SQLiteActionStore()

    def plan(self, user_request: str) -> AgentPlan:
        original_action = self.analyze_and_plan(user_request)
        current_state = self.capture_current_state(original_action)
        original_rollback = self.create_rollback_plan(original_action, current_state)
        gate_result = self.decide_gate(original_action, original_rollback)
        final_action = gate_result.safe_alternative or original_action
        return AgentPlan(
            user_request=user_request,
            original_action=original_action,
            rollback_plan=original_rollback,
            gate_result=gate_result,
            final_action=final_action,
        )

    def execute(self, plan: AgentPlan) -> dict[str, Any]:
        if plan.gate_result.gate_decision is GateDecision.APPROVAL_REQUIRED:
            action_id = self.store.create_action_log(
                plan.user_request,
                plan.original_action,
                plan.final_action,
                plan.rollback_plan,
                plan.gate_result,
                ActionStatus.CANCELLED,
            )
            return {
                "action_id": action_id,
                "status": ActionStatus.CANCELLED.value,
                "message": "복구 가능성이 제한적이어서 사용자 승인 전에는 실행하지 않았습니다.",
            }

        final_state = self.capture_current_state(plan.final_action)
        final_rollback = self.create_rollback_plan(plan.final_action, final_state)
        result = self.execute_action(plan.final_action)
        resolved_rollback = self.resolve_runtime_rollback(final_rollback, result)
        status = (
            ActionStatus.TRANSFORMED
            if plan.original_action.action_type is not plan.final_action.action_type
            else ActionStatus.EXECUTED
        )
        action_id = self.store.create_action_log(
            plan.user_request,
            plan.original_action,
            plan.final_action,
            resolved_rollback,
            plan.gate_result,
            status,
        )
        return {
            "action_id": action_id,
            "status": status.value,
            "message": self._success_message(plan.original_action, result, plan.final_action),
            "result": result,
            "rollback_plan": resolved_rollback.to_dict(),
            "gate_result": plan.gate_result.to_dict(),
        }

    def run(self, user_request: str) -> dict[str, Any]:
        plan = self.plan(user_request)
        execution = self.execute(plan)
        return {"plan": plan.to_dict(), "execution": execution}

    def rollback(self, action_id: int) -> dict[str, Any]:
        log = self.store.get_action_log(action_id)
        if not log:
            raise ValueError(f"action log not found: {action_id}")
        if log["status"] == ActionStatus.ROLLED_BACK.value:
            return {
                "action_id": action_id,
                "status": ActionStatus.ROLLED_BACK.value,
                "message": "이미 되돌린 작업입니다.",
            }
        rollback_payload = json.loads(log["rollback_payload"])
        rollback_type = RollbackType(rollback_payload["rollback_type"])
        arguments = rollback_payload["rollback_arguments"]
        result = self.execute_rollback(rollback_type, arguments)
        self.store.mark_rolled_back(action_id)
        return {
            "action_id": action_id,
            "status": ActionStatus.ROLLED_BACK.value,
            "message": "저장된 Rollback Plan에 따라 이전 상태로 복구했습니다.",
            "result": result,
        }

    def analyze_and_plan(self, user_request: str) -> PlannedAction:
        text = user_request.strip()
        if not text:
            raise ValueError("user_request must not be empty")

        if "완료" in text and any(word in text for word in ["정리", "삭제", "지워"]):
            return PlannedAction(
                action_type=ActionType.DELETE_TODO,
                arguments={"status": "done"},
                description="완료된 Todo를 삭제합니다.",
            )

        if any(word in text for word in ["공지", "알림"]) and any(
            word in text for word in ["보내", "전송", "알려"]
        ):
            notice = self._extract_notice(text)
            return PlannedAction(
                action_type=ActionType.SEND_NOTICE,
                arguments=notice,
                description=f"{notice['target']}에게 {notice['title']} 공지를 전송합니다.",
            )

        if "일정" in text and any(word in text for word in ["추가", "생성", "등록", "짜줘", "만들어"]):
            title = self._extract_title(text, fallback="새 일정")
            start_time = self._extract_datetime(text)
            end_time = self._add_one_hour(start_time)
            return PlannedAction(
                action_type=ActionType.CREATE_SCHEDULE,
                arguments={
                    "title": title,
                    "start_time": start_time,
                    "end_time": end_time,
                },
                description=f"{title} 일정을 생성합니다.",
            )

        if "일정" in text and any(word in text for word in ["바꿔", "변경", "수정"]):
            title = self._extract_title(text, fallback="일정")
            start_time = self._extract_datetime(text)
            end_time = self._add_one_hour(start_time)
            schedule = self.store.find_schedule_by_title(title)
            if not schedule:
                schedule = self.store.fetch_schedules()[0] if self.store.fetch_schedules() else None
            if not schedule:
                raise ValueError("수정할 일정을 찾지 못했습니다.")
            return PlannedAction(
                action_type=ActionType.UPDATE_SCHEDULE,
                arguments={
                    "id": schedule["id"],
                    "start_time": start_time,
                    "end_time": end_time,
                },
                description=f"{schedule['title']} 일정을 수정합니다.",
            )

        if "일정" in text and any(word in text for word in ["삭제", "지워", "취소"]):
            title = self._extract_title(text, fallback="일정")
            schedule = self.store.find_schedule_by_title(title)
            if not schedule:
                raise ValueError("삭제할 일정을 찾지 못했습니다.")
            return PlannedAction(
                action_type=ActionType.DELETE_SCHEDULE,
                arguments={"ids": [schedule["id"]]},
                description=f"{schedule['title']} 일정을 삭제합니다.",
            )

        if "할 일" in text and any(word in text for word in ["추가", "생성", "등록"]):
            title = self._extract_title(text, fallback="새 할 일")
            return PlannedAction(
                action_type=ActionType.CREATE_TODO,
                arguments={"title": title},
                description=f"{title} Todo를 생성합니다.",
            )

        if "할 일" in text and any(word in text for word in ["바꿔", "변경", "수정"]):
            todos = self.store.fetch_todos()
            if not todos:
                raise ValueError("수정할 Todo를 찾지 못했습니다.")
            title = self._extract_title(text, fallback=todos[0]["title"])
            return PlannedAction(
                action_type=ActionType.UPDATE_TODO,
                arguments={"id": todos[0]["id"], "title": title},
                description=f"{todos[0]['title']} Todo를 수정합니다.",
            )

        raise ValueError("지원하지 않는 요청입니다. Todo 또는 일정 생성/수정/삭제를 요청해 주세요.")

    def decide_gate(
        self, action: PlannedAction, rollback_plan: RollbackPlan
    ) -> GateResult:
        if rollback_plan.recovery_level is RecoveryLevel.FULLY_REVERSIBLE:
            return GateResult(
                gate_decision=GateDecision.EXECUTE,
                reason="이 작업은 완전히 복구 가능하므로 자동 실행할 수 있습니다.",
            )
        if rollback_plan.recovery_level is RecoveryLevel.PARTIALLY_REVERSIBLE:
            return GateResult(
                gate_decision=GateDecision.APPROVAL_REQUIRED,
                reason="이 작업은 일부만 복구 가능하므로 사용자 승인이 필요합니다.",
            )
        if action.action_type is ActionType.SEND_NOTICE:
            safe_action = PlannedAction(
                action_type=ActionType.CREATE_NOTICE_DRAFT,
                arguments=action.arguments,
                description="공지 전송 대신 공지 초안을 생성합니다.",
            )
            return GateResult(
                gate_decision=GateDecision.TRANSFORM_TO_SAFE_ACTION,
                reason="공지 전송은 복구가 어려우므로 초안 생성으로 변환합니다.",
                safe_alternative=safe_action,
            )
        return GateResult(
            gate_decision=GateDecision.APPROVAL_REQUIRED,
            reason="복구 불가능한 작업이므로 사용자 승인이 필요합니다.",
        )

    def capture_current_state(self, action: PlannedAction) -> Any:
        if action.action_type is ActionType.UPDATE_TODO:
            return self.store.get_todo(int(action.arguments["id"]))
        if action.action_type is ActionType.DELETE_TODO:
            status = action.arguments.get("status")
            if status:
                return self.store.fetch_todos(status=status)
            return [self.store.get_todo(todo_id) for todo_id in action.arguments["ids"]]
        if action.action_type is ActionType.UPDATE_SCHEDULE:
            return self.store.get_schedule(int(action.arguments["id"]))
        if action.action_type is ActionType.DELETE_SCHEDULE:
            return [
                self.store.get_schedule(schedule_id)
                for schedule_id in action.arguments["ids"]
            ]
        return None

    def create_rollback_plan(self, action: PlannedAction, current_state: Any) -> RollbackPlan:
        if action.action_type is ActionType.CREATE_TODO:
            return RollbackPlan(
                RollbackType.DELETE_CREATED_TODO,
                {"target": "created_todo_id"},
                True,
                RecoveryLevel.FULLY_REVERSIBLE,
                "생성된 Todo ID를 이용해 삭제하면 되돌릴 수 있습니다.",
            )
        if action.action_type is ActionType.UPDATE_TODO:
            return RollbackPlan(
                RollbackType.RESTORE_UPDATED_TODO,
                {"backup_data": current_state},
                current_state is not None,
                RecoveryLevel.FULLY_REVERSIBLE if current_state is not None else RecoveryLevel.IRREVERSIBLE,
                "수정 전 Todo 데이터를 백업했기 때문에 복구할 수 있습니다.",
            )
        if action.action_type is ActionType.DELETE_TODO:
            return RollbackPlan(
                RollbackType.RESTORE_DELETED_TODO,
                {"backup_data": current_state or []},
                bool(current_state),
                RecoveryLevel.FULLY_REVERSIBLE if current_state else RecoveryLevel.IRREVERSIBLE,
                "삭제 전 Todo 데이터를 백업했기 때문에 복구할 수 있습니다.",
            )
        if action.action_type is ActionType.CREATE_SCHEDULE:
            return RollbackPlan(
                RollbackType.DELETE_CREATED_SCHEDULE,
                {"target": "created_schedule_id"},
                True,
                RecoveryLevel.FULLY_REVERSIBLE,
                "생성된 일정 ID를 이용해 삭제하면 되돌릴 수 있습니다.",
            )
        if action.action_type is ActionType.UPDATE_SCHEDULE:
            return RollbackPlan(
                RollbackType.RESTORE_UPDATED_SCHEDULE,
                {"backup_data": current_state},
                current_state is not None,
                RecoveryLevel.FULLY_REVERSIBLE if current_state is not None else RecoveryLevel.IRREVERSIBLE,
                "수정 전 일정 정보를 백업했기 때문에 복구할 수 있습니다.",
            )
        if action.action_type is ActionType.DELETE_SCHEDULE:
            return RollbackPlan(
                RollbackType.RESTORE_DELETED_SCHEDULE,
                {"backup_data": current_state or []},
                bool(current_state),
                RecoveryLevel.FULLY_REVERSIBLE if current_state else RecoveryLevel.IRREVERSIBLE,
                "삭제 전 일정 정보를 백업했기 때문에 복구할 수 있습니다.",
            )
        if action.action_type is ActionType.CREATE_NOTICE_DRAFT:
            return RollbackPlan(
                RollbackType.DELETE_NOTICE_DRAFT,
                {"target": "created_notice_draft_id"},
                True,
                RecoveryLevel.FULLY_REVERSIBLE,
                "생성된 공지 초안을 삭제하면 되돌릴 수 있습니다.",
            )
        if action.action_type is ActionType.SEND_NOTICE:
            return RollbackPlan(
                RollbackType.NOT_AVAILABLE,
                {},
                False,
                RecoveryLevel.IRREVERSIBLE,
                "공지 전송은 외부 사용자에게 전달된 후 완전히 회수할 수 없습니다.",
            )
        return RollbackPlan(
            RollbackType.NOT_AVAILABLE,
            {},
            False,
            RecoveryLevel.IRREVERSIBLE,
            "이 작업은 되돌리기 어렵습니다.",
        )

    def execute_action(self, action: PlannedAction) -> dict[str, Any]:
        args = action.arguments
        if action.action_type is ActionType.CREATE_TODO:
            todo = self.store.create_todo(title=args["title"])
            return {"created_todo_id": todo["id"], "todo": todo}
        if action.action_type is ActionType.UPDATE_TODO:
            todo = self.store.update_todo(int(args["id"]), **{k: v for k, v in args.items() if k != "id"})
            return {"updated_todo_id": todo["id"], "todo": todo}
        if action.action_type is ActionType.DELETE_TODO:
            ids = [item["id"] for item in self.store.fetch_todos(args["status"])] if "status" in args else args["ids"]
            deleted = self.store.delete_todos([int(todo_id) for todo_id in ids])
            return {"deleted_count": len(deleted), "deleted": deleted}
        if action.action_type is ActionType.CREATE_SCHEDULE:
            schedule = self.store.create_schedule(
                title=args["title"],
                start_time=args["start_time"],
                end_time=args["end_time"],
            )
            return {"created_schedule_id": schedule["id"], "schedule": schedule}
        if action.action_type is ActionType.UPDATE_SCHEDULE:
            schedule = self.store.update_schedule(
                int(args["id"]),
                **{k: v for k, v in args.items() if k != "id"},
            )
            return {"updated_schedule_id": schedule["id"], "schedule": schedule}
        if action.action_type is ActionType.DELETE_SCHEDULE:
            deleted = self.store.delete_schedules([int(item) for item in args["ids"]])
            return {"deleted_count": len(deleted), "deleted": deleted}
        if action.action_type is ActionType.CREATE_NOTICE_DRAFT:
            notice = self.store.create_notice_draft(
                target=args["target"],
                title=args["title"],
                content=args["content"],
            )
            return {"created_notice_draft_id": notice["id"], "notice": notice}
        if action.action_type is ActionType.SEND_NOTICE:
            raise ValueError("send_notice is irreversible and must pass through the execution gate")
        raise ValueError(f"unsupported action: {action.action_type}")

    def resolve_runtime_rollback(
        self, rollback: RollbackPlan, result: dict[str, Any]
    ) -> RollbackPlan:
        args = dict(rollback.rollback_arguments)
        if rollback.rollback_type is RollbackType.DELETE_CREATED_TODO:
            args["target"] = result["created_todo_id"]
        if rollback.rollback_type is RollbackType.DELETE_CREATED_SCHEDULE:
            args["target"] = result["created_schedule_id"]
        if rollback.rollback_type is RollbackType.DELETE_NOTICE_DRAFT:
            args["target"] = result["created_notice_draft_id"]
        return RollbackPlan(
            rollback.rollback_type,
            args,
            rollback.rollback_available,
            rollback.recovery_level,
            rollback.reason,
        )

    def execute_rollback(
        self, rollback_type: RollbackType, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if rollback_type is RollbackType.DELETE_CREATED_TODO:
            deleted = self.store.delete_todos([int(arguments["target"])])
            return {"deleted": deleted}
        if rollback_type is RollbackType.RESTORE_UPDATED_TODO:
            restored = self.store.restore_todos([arguments["backup_data"]])
            return {"restored": restored}
        if rollback_type is RollbackType.RESTORE_DELETED_TODO:
            restored = self.store.restore_todos(arguments["backup_data"])
            return {"restored": restored}
        if rollback_type is RollbackType.DELETE_CREATED_SCHEDULE:
            deleted = self.store.delete_schedules([int(arguments["target"])])
            return {"deleted": deleted}
        if rollback_type is RollbackType.RESTORE_UPDATED_SCHEDULE:
            restored = self.store.restore_schedules([arguments["backup_data"]])
            return {"restored": restored}
        if rollback_type is RollbackType.RESTORE_DELETED_SCHEDULE:
            restored = self.store.restore_schedules(arguments["backup_data"])
            return {"restored": restored}
        if rollback_type is RollbackType.DELETE_NOTICE_DRAFT:
            deleted = self.store.delete_notices([int(arguments["target"])])
            return {"deleted": deleted}
        raise ValueError("rollback is not available for this action")

    def _success_message(
        self,
        original_action: PlannedAction,
        result: dict[str, Any],
        final_action: PlannedAction,
    ) -> str:
        if (
            original_action.action_type is ActionType.SEND_NOTICE
            and final_action.action_type is ActionType.CREATE_NOTICE_DRAFT
        ):
            return "공지 전송은 복구가 어려운 작업이므로 바로 전송하지 않고 공지 초안을 생성했습니다."
        if final_action.action_type is ActionType.CREATE_TODO:
            return "Todo가 생성되었습니다."
        if final_action.action_type is ActionType.UPDATE_TODO:
            return "Todo가 수정되었습니다."
        if final_action.action_type is ActionType.DELETE_TODO:
            return f"Todo {result['deleted_count']}개가 삭제되었습니다."
        if final_action.action_type is ActionType.CREATE_SCHEDULE:
            return "일정이 생성되었습니다."
        if final_action.action_type is ActionType.UPDATE_SCHEDULE:
            return "일정이 수정되었습니다."
        if final_action.action_type is ActionType.DELETE_SCHEDULE:
            return f"일정 {result['deleted_count']}개가 삭제되었습니다."
        if final_action.action_type is ActionType.CREATE_NOTICE_DRAFT:
            return "공지 초안이 생성되었습니다."
        return "작업이 실행되었습니다."

    def _extract_title(self, text: str, fallback: str) -> str:
        cleaned = re.sub(r"(내일|오늘|오전|오후|\d+시에|\d+시|\d+분|금요일|토요일|일요일)", "", text)
        cleaned = re.sub(r"(일정좀|일정|할 일|todo|Todo|추가해줘|추가|생성|등록|짜줘|만들어줘|만들어|바꿔줘|바꿔|변경|수정|삭제|지워|취소|라는|이라는|을|를|에)", " ", cleaned)
        title = " ".join(cleaned.split()).strip()
        return title or fallback

    def _extract_datetime(self, text: str) -> str:
        base = datetime(2026, 6, 21, 9, 0)
        if "내일" in text:
            base += timedelta(days=1)
        hour_match = re.search(r"(\d{1,2})\s*시", text)
        hour = int(hour_match.group(1)) if hour_match else 9
        if "오후" in text and hour < 12:
            hour += 12
        if "오전" in text and hour == 12:
            hour = 0
        return base.replace(hour=hour, minute=0).strftime("%Y-%m-%d %H:%M")

    def _add_one_hour(self, start_time: str) -> str:
        parsed = datetime.strptime(start_time, "%Y-%m-%d %H:%M")
        return (parsed + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")

    def _extract_notice(self, text: str) -> dict[str, str]:
        target = "team_members" if any(word in text for word in ["팀원", "팀"]) else "all"
        if "회의" in text and "취소" in text:
            title = "회의 취소 안내"
            content = "내일 예정된 회의는 취소되었습니다."
        else:
            title = "공지 초안"
            content = re.sub(r"(공지|알림|보내줘|전송해줘|알려줘)", " ", text)
            content = " ".join(content.split()).strip() or text
        return {"target": target, "title": title, "content": content}


def demo_agent() -> RollbackFirstAgent:
    store = SQLiteActionStore()
    store.seed_demo_data()
    return RollbackFirstAgent(store)
