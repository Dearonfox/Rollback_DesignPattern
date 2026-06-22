# Task II 제출 문서

## 선택 항목 1

### 항목명

AI Agentic Design Pattern 새로운 것 제안 및 구현

### 프로젝트/기여 제목

Rollback-Gated Agent Pattern: 복구 가능성 기반 실행 게이트 패턴

### 구현 또는 기여 내용 요약

본 프로젝트에서는 기존 ReAct 패턴의 한계를 보완하기 위해 **Rollback-Gated Agent Pattern**을 제안하고 구현했습니다.

ReAct 패턴은 `Reason -> Act -> Observe` 구조를 통해 추론과 행동을 반복하지만, 외부 도구 실행으로 시스템 상태가 변경되는 경우 해당 행동이 되돌릴 수 있는지에 대한 구조를 명시적으로 포함하지 않습니다.

Rollback-Gated Agent Pattern은 AI Agent가 외부 도구를 실행하기 전에 먼저 해당 행동의 복구 가능성을 평가하고, 복구 가능성에 따라 실행 여부를 결정하는 패턴입니다.

핵심 동작은 다음과 같습니다.

```text
복구 가능       -> 자동 실행
부분 복구 가능  -> 사용자 승인 필요
복구 불가능     -> 안전한 대체 작업으로 변환
```

구현 예시는 자연어 기반 Todo / Schedule / Notice 관리 Agent입니다.

지원 기능은 다음과 같습니다.

- Todo 생성, 수정, 삭제
- Schedule 생성, 수정, 삭제
- Notice 전송 요청 분석
- Notice 전송이 복구 불가능한 작업임을 판단
- Notice 전송을 Notice 초안 생성으로 자동 변환
- 실행 기록 저장
- 실행된 작업 Rollback

예를 들어 사용자가 다음과 같이 요청한다고 가정합니다.

```text
팀원들에게 내일 회의 취소됐다고 공지 보내줘
```

Agent는 이를 처음에는 `send_notice` 작업으로 분석합니다. 하지만 공지 전송은 외부 사용자에게 전달된 후 완전히 회수하기 어렵기 때문에 `irreversible`로 판단하고, 실제 실행 작업을 `create_notice_draft`로 변환합니다.

```text
original_action: send_notice
recovery_level: irreversible
gate_decision: transform_to_safe_action
final_action: create_notice_draft
```

이를 통해 단순한 Undo 기능이 아니라, **복구 가능성 평가 -> 실행 게이트 판단 -> 안전한 대체 작업 변환**이라는 새로운 Agentic Design Pattern을 구현했습니다.

### 사용 기술 스택

- Python
- FastAPI
- SQLite
- React
- TypeScript
- Vite
- Axios
- unittest

### GitHub Repository 링크

https://github.com/Dearonfox/Rollback_DesignPattern.git

### 실행 방법 또는 확인 방법

백엔드 실행:

```powershell
cd C:\Users\me\dogfoot\오픈소스\task2\designpattern
python -m uvicorn rollback_first_agent.backend.main:app --reload
```

프론트엔드 실행:

```powershell
cd C:\Users\me\dogfoot\오픈소스\task2\designpattern\rollback_first_agent\frontend
npm run dev
```

CLI 데모 실행:

```powershell
cd C:\Users\me\dogfoot\오픈소스\task2\designpattern
python -m rollback_first_agent.demo "팀원들에게 내일 회의 취소됐다고 공지 보내줘"
```

테스트 실행:

```powershell
cd C:\Users\me\dogfoot\오픈소스\task2\designpattern
python -m unittest discover -s tests
```

### 결과물 링크

- GitHub Repository: https://github.com/Dearonfox/Rollback_DesignPattern.git

### 본인이 직접 수행한 부분

- ReAct 패턴의 한계와 상태 변경형 Agent의 문제점을 분석했습니다.
- Rollback-Gated Agent Pattern의 핵심 아이디어를 설계했습니다.
- 복구 가능성 평가, Execution Gate, 안전한 대체 작업 변환 구조를 정의했습니다.
- Todo / Schedule / Notice 관리 서비스라는 구현 주제를 선정했습니다.
- `send_notice`를 복구 불가능 작업으로 보고 `create_notice_draft`로 변환하는 시나리오를 설계했습니다.
- 구현 과정에서는 AI 도구를 활용하여 FastAPI, React, SQLite 기반 코드를 생성하고 수정했습니다.
- 생성된 코드의 동작을 직접 실행하며 오류를 확인하고 수정 방향을 정했습니다.
- 프론트엔드 화면, 백엔드 API, Action Ledger, Rollback 동작이 패턴 의도와 맞는지 검증했습니다.
- 테스트 실행 결과를 확인하고 제출 문서를 정리했습니다.

---

## 선택 항목 2

### 항목명

특정 서비스 Clone Coding

### 프로젝트/기여 제목

Netflix Clone Coding

### 구현 또는 기여 내용 요약

Netflix 서비스를 클론 코딩하여 Front-End와 Back-End를 모두 포함한 웹 서비스를 구현했습니다.

주요 구현 내용은 다음과 같습니다.

- Netflix 스타일 메인 화면 구현
- 영화 / 콘텐츠 목록 UI 구현
- 콘텐츠 상세 정보 화면 구현
- 로그인 또는 사용자 인증 기능 구현
- 콘텐츠 데이터 조회 API 구현
- Front-End와 Back-End 연동
- Database를 통한 콘텐츠 또는 사용자 데이터 관리
- 반응형 UI 구성

본 프로젝트는 단순 정적 페이지가 아니라, Front-End와 Back-End가 분리된 구조로 구현되었으며 API를 통해 데이터를 주고받도록 구성했습니다.

### 사용 기술 스택

`TODO: 실제 사용 기술 스택 입력`

예시:

- Front-End: React, TypeScript, Vite
- Back-End: Node.js / Express 또는 FastAPI
- Database: MongoDB / SQLite / PostgreSQL
- Styling: CSS / Tailwind CSS / Styled Components
- API 통신: Axios / Fetch API

### GitHub Repository 링크

`TODO: Netflix Clone GitHub Repository 링크 입력`

### 실행 방법 또는 확인 방법

`TODO: 실제 프로젝트 실행 방법 입력`

예시:

프론트엔드 실행:

```powershell
cd frontend
npm install
npm run dev
```

백엔드 실행:

```powershell
cd backend
npm install
npm run dev
```

또는:

```powershell
python -m uvicorn main:app --reload
```

### 결과물 링크

- GitHub Repository: `TODO: GitHub Repository 링크 입력`

### 본인이 직접 수행한 부분

- Netflix Clone Coding의 화면 구성과 주요 기능 범위를 정했습니다.
- Front-End와 Back-End를 모두 포함하는 구조로 프로젝트 방향을 잡았습니다.
- 구현 과정에서는 AI 도구를 활용하여 UI, API, 데이터 처리 코드 작성을 보조받았습니다.
- 생성된 코드의 실행 결과를 확인하고 필요한 수정 사항을 반영했습니다.
- Front-End와 Back-End 연동 여부를 확인했습니다.
- 실행 방법과 제출 문서를 정리했습니다.
