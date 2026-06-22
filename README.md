# Rollback-Gated Agent

복구 가능성을 기준으로 AI Agent의 행동 실행 여부를 결정하는 Agentic Design Pattern 구현 프로젝트입니다.

## Pattern

**Rollback-Gated Agent Pattern**  
한국어: **복구 가능성 기반 실행 게이트 패턴**

> AI 에이전트가 외부 도구를 실행하기 전에 해당 행동의 복구 가능성을 평가하고, 복구 가능한 작업만 자동 실행하며, 복구 불가능한 작업은 사용자 승인 또는 안전한 대체 작업으로 변환하는 패턴.

## Core Question

```text
이 작업은 실행 후 되돌릴 수 있는가?
```

Gate decision:

```text
fully_reversible     -> execute
partially_reversible -> approval_required
irreversible         -> transform_to_safe_action
```

## Why Not Just ReAct?

ReAct는 `Reason -> Act -> Observe`를 반복하는 강력한 패턴입니다. 하지만 외부 상태를 변경하는 도구 실행에서, 그 행동이 복구 가능한지 여부를 명시적으로 판단하지 않습니다.

Rollback-Gated Agent는 행동 전에 복구 가능성을 평가하고, 실행 게이트를 통과한 행동만 실행합니다.

## Flow

```text
User Request
    ↓
Request Analyzer
    ↓
Action Planner
    ↓
Rollback Planner
    ↓
Recovery Feasibility Checker
    ↓
Execution Gate
    ├─ execute
    ├─ approval_required
    └─ transform_to_safe_action
    ↓
Tool Executor
    ↓
Action Ledger
    ↓
Rollback Executor
```

## Implementation

구현 예시는 **자연어 기반 Todo / Schedule / Notice 관리 에이전트**입니다.

지원 작업:

- `create_todo`
- `update_todo`
- `delete_todo`
- `create_schedule`
- `update_schedule`
- `delete_schedule`
- `send_notice`
- `create_notice_draft`

핵심 시나리오:

```text
팀원들에게 내일 회의 취소됐다고 공지 보내줘
```

Agent 판단:

```text
original_action: send_notice
recovery_level: irreversible
gate_decision: transform_to_safe_action
final_action: create_notice_draft
```

즉, 공지 전송은 외부 사용자에게 전달되면 완전히 회수할 수 없으므로 바로 전송하지 않고 공지 초안을 생성합니다.

## Run Core Demo

복구 가능한 일정 생성:

```powershell
python -m rollback_first_agent.demo "내일 오후 3시에 운영체제 공부 일정 추가해줘"
```

복구 가능한 Todo 삭제:

```powershell
python -m rollback_first_agent.demo "완료된 할 일 정리해줘"
```

복구 불가능한 공지 전송의 안전 변환:

```powershell
python -m rollback_first_agent.demo "팀원들에게 내일 회의 취소됐다고 공지 보내줘"
```

## Run Backend

```powershell
pip install -r rollback_first_agent/requirements.txt
python -m uvicorn rollback_first_agent.backend.main:app --reload
```

## Run Frontend

```powershell
cd rollback_first_agent/frontend
npm install
npm run dev
```

## Test

```powershell
python -m unittest tests.test_rollback_first_agent
```

전체 테스트:

```powershell
python -m unittest discover -s tests
```

## Difference From ReAct

| 구분 | ReAct Pattern | Rollback-Gated Agent Pattern |
| --- | --- | --- |
| 핵심 구조 | 추론 후 행동 | 복구 가능성 평가 후 행동 |
| 행동 전 검토 | 제한적 | recovery level과 gate decision 확인 |
| 실패 대응 | 사후 처리 중심 | 실행 전 차단 또는 안전 대체 |
| 복구 불가능 작업 | 실행될 수 있음 | 안전한 대체 작업으로 변환 |
| 구현 핵심 | Thought-Action-Observation | Recovery-Gate-Ledger |

## Submission Point

이 프로젝트는 단순 Undo 기능이 아니라, **복구 가능성 평가 -> 실행 게이트 판단 -> 안전한 대체 작업 변환**을 구현합니다.

핵심 기여:

- `RecoveryLevel`: fully_reversible / partially_reversible / irreversible
- `GateDecision`: execute / approval_required / transform_to_safe_action
- irreversible한 `send_notice`를 `create_notice_draft`로 자동 변환
- original_action과 final_action을 Action Ledger에 함께 저장
- 실행한 final_action은 rollback plan으로 되돌릴 수 있음
