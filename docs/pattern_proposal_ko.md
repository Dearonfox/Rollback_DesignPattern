# Rollback-Gated Agent Pattern 제안서

## 1. 패턴명

**Rollback-Gated Agent Pattern**

한국어 이름:

**복구 가능성 기반 실행 게이트 패턴**

## 2. 한 줄 정의

Rollback-Gated Agent Pattern은 AI 에이전트가 외부 도구를 실행하기 전에 해당 행동의 복구 가능성을 평가하고, 복구 가능한 작업만 자동 실행하며, 복구 불가능한 작업은 안전한 대체 작업으로 변환하는 Agentic Design Pattern이다.

## 3. 핵심 질문

```text
이 작업은 실행 후 되돌릴 수 있는가?
```

복구 가능성에 따른 실행 정책:

```text
복구 가능       -> 실행
부분 복구 가능  -> 사용자 승인 필요
복구 불가능     -> 안전한 대체 작업으로 변환
```

## 4. ReAct와의 차이

ReAct는 다음 구조를 가진다.

```text
Reason -> Act -> Observe
```

하지만 ReAct는 외부 도구 실행이 실제 시스템 상태를 바꾸는 경우, 그 행동이 복구 가능한지 명시적으로 판단하지 않는다.

Rollback-Gated Agent는 행동 전에 Recovery Feasibility를 평가하고 Execution Gate를 통과한 행동만 실행한다.

## 5. 패턴 구조

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

## 6. 구현 주제

**Rollback-Gated Task Agent**

자연어 기반 Todo / Schedule / Notice 관리 에이전트이다.

지원 작업:

- Todo 생성, 수정, 삭제
- Schedule 생성, 수정, 삭제
- Notice 전송
- Notice 초안 생성

## 7. Recovery Level

```text
FULLY_REVERSIBLE
PARTIALLY_REVERSIBLE
IRREVERSIBLE
```

| 작업 | Recovery Level | 처리 |
| --- | --- | --- |
| Todo 생성 | fully_reversible | 생성된 Todo 삭제로 복구 |
| Todo 삭제 | fully_reversible | 삭제 전 백업으로 복구 |
| Schedule 생성 | fully_reversible | 생성된 일정 삭제로 복구 |
| Schedule 수정 | fully_reversible | 수정 전 일정으로 복구 |
| Notice 전송 | irreversible | Notice 초안 생성으로 변환 |
| Notice 초안 생성 | fully_reversible | 생성된 초안 삭제로 복구 |

## 8. Gate Decision

```text
execute
approval_required
transform_to_safe_action
```

핵심 예시:

```text
사용자: 팀원들에게 내일 회의 취소됐다고 공지 보내줘

original_action: send_notice
recovery_level: irreversible
gate_decision: transform_to_safe_action
final_action: create_notice_draft
```

## 9. 구현 설명

핵심 구현:

- `rollback_first_agent/core.py`
- `rollback_first_agent/backend/main.py`
- `rollback_first_agent/frontend/src/main.tsx`

주요 모델:

- `ActionType`
- `RollbackType`
- `RecoveryLevel`
- `GateDecision`
- `GateResult`
- `AgentPlan`

Action Ledger는 다음 정보를 저장한다.

- user_request
- original_action_type
- original_action_payload
- final_action_type
- final_action_payload
- recovery_level
- gate_decision
- rollback_payload
- status

## 10. 실행 예시

```powershell
python -m rollback_first_agent.demo "팀원들에게 내일 회의 취소됐다고 공지 보내줘"
```

예상 결과:

```text
send_notice는 irreversible이므로 바로 실행하지 않는다.
create_notice_draft로 변환한다.
공지 초안을 생성한다.
생성된 초안은 delete_notice_draft로 rollback 가능하다.
```

## 11. 결론

Rollback-Gated Agent Pattern은 단순 Undo 기능이 아니라, AI 에이전트의 행동을 복구 가능성 기준으로 통제하는 실행 패턴이다.

핵심 차별점:

```text
복구 가능성 평가 -> 실행 게이트 판단 -> 안전한 대체 작업 변환
```

따라서 본 프로젝트는 ReAct의 한계를 보완하는 새로운 Agentic Design Pattern 제안 및 구현으로 설명할 수 있다.

