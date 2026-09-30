# 아키텍처

## 1. 책임 경계

### Codex

의미 해석이 필요한 작업을 담당합니다.

- repository 탐색
- Task 해석
- 변경 영향 추론
- Plan 생성
- 구현
- 실패 원인 진단
- 코드 / 설계 Review
- Exec 초안

### DevFlow

결정적으로 제어할 수 있는 영역을 담당합니다.

- workflow state
- Codex process 실행
- structured output parsing
- routing policy
- build / test / lint
- timeout
- retry limit
- artifact path
- run log
- metric

원칙:

> LLM이 잘하는 의미 해석은 Codex에게 맡기고, 정책과 상태 전이는 프로그램이 통제한다.

## 2. Execution Backend

초기 구조:

~~~text
DevFlow
   |
   v
CodexExecutionBackend
   |
   +--> CodexCliBackend
~~~

Workflow가 특정 실행 방식에 직접 묶이지 않도록 내부 경계를 둡니다.

향후 필요할 경우:

~~~text
CodexExecutionBackend
   |
   +--> CodexCliBackend    현재 목표
   +--> ApiBackend         향후 가능
   +--> OtherBackend       향후 가능
~~~

첫 구현에서는 CodexCliBackend만 구현합니다.

### 2.1 역할 분리와 Subagent는 같은 개념이 아니다

Planner, Implementer, Reviewer처럼 역할을 나누기 위해 반드시 OpenAI의 native Subagent 기능이 필요한 것은 아닙니다.

V1에서는 DevFlow가 필요한 역할마다 **독립적인 `codex exec` 프로세스**를 실행합니다.

~~~text
DevFlow
  |
  +-- codex exec #1  → Planner
  +-- codex exec #2  → Implementer
  +-- codex exec #3  → General Reviewer
  +-- codex exec #4  → Database Reviewer
  +-- codex exec #5  → Reliability Reviewer
~~~

각 worker는 같은 Codex CLI를 사용하지만 별도의 실행 context를 가집니다. 사용자가 Codex 창을 여러 개 직접 띄우는 것이 아니라 DevFlow가 worker의 생성, 입력, 종료, 결과 수집을 관리합니다.

따라서 초기 구조는 다음과 같이 구분합니다.

~~~text
Role
= Planner / Implementer / Reviewer처럼 "무슨 일을 맡는가"

CLI Worker
= DevFlow가 특정 Role을 수행하도록 실행한 독립 codex exec 프로세스

Native Subagent
= OpenAI Agent runtime 내부에서 parent agent가 spawn/delegate하는 별도 agent
~~~

V1의 역할 분리는 CLI Worker로 충분합니다. Native Subagent는 독립 context, delegation, 병렬 협업이 실제로 추가 이점을 만든다는 근거가 생긴 뒤 검토합니다.

특히 초기에는 코드 변경을 여러 worker가 동시에 수행하지 않습니다.

~~~text
Implementation
→ 단일 Codex Worker

Independent Review
→ 필요 시 여러 Read-only Codex Worker
~~~

이렇게 하면 같은 파일에 대한 병렬 수정 충돌을 피하면서도 review 관점은 분리할 수 있습니다.

## 3. 전체 흐름

~~~text
User Task
    |
    v
Scout / Classifier
    |
    | structured signals
    v
Policy Engine
    |
    +----------------+----------------+
    |                |                |
  SIMPLE           MEDIUM           COMPLEX
    |                |                |
 implement         plan             plan
 validate          implement        implement
 finish            validate         validate
                   review           specialized review
                   finish           bounded repair
                                    exec
~~~

모든 경로를 첫 구현에서 동시에 만들 필요는 없습니다.

## 4. Task 분석

Codex에게 단순히 "이거 어려워?"라고 묻지 않습니다.

Repository를 읽은 뒤 workflow 결정에 필요한 semantic signal을 구조화해서 반환하도록 합니다.

예시:

~~~json
{
  "scope": "multi-module",
  "database_change": true,
  "transaction_change": true,
  "concurrency": false,
  "async_processing": true,
  "external_integration": false,
  "migration": false,
  "regression_risk": "high",
  "suggested_reviews": ["database", "reliability"]
}
~~~

정확한 schema는 구현하면서 확정합니다.

핵심은 다음 분리입니다.

> Codex는 semantic signal을 추론한다.  
> DevFlow는 signal을 바탕으로 deterministic routing policy를 적용한다.

## 5. Workflow 후보

### Simple

~~~text
Implement → Validate → Finish
~~~

### Medium

~~~text
Plan → Implement → Validate → General Review → Finish
~~~

### Complex

~~~text
Plan
→ Implement
→ Validate
→ 필요한 Specialized Review
→ 필요 시 Repair
→ Re-validate
→ Exec
~~~

SIMPLE / MEDIUM / COMPLEX는 영구적인 제품 용어가 아니라 routing을 위한 초기 모델입니다. Eval 결과에 따라 바꿀 수 있습니다.

## 6. Skill

Skill은 Codex가 반복 업무를 수행할 때 참고하는 절차입니다.

후보:

~~~text
skills/
  feature-planning/
  backend-review/
  database-review/
  reliability-review/
  test-review/
  execution-documentation/
~~~

예:

database-review:

- query path
- transaction boundary
- lock
- index 영향
- 데이터 정합성

reliability-review:

- retry
- idempotency
- duplicate delivery
- failure / recovery

Skill은 workflow state를 관리하지 않습니다. **어떤 일을 어떻게 수행할지에 대한 지식**을 제공합니다.

## 7. Deterministic Validation

프로젝트별 validation command를 설정 가능하게 합니다.

예:

~~~text
./gradlew test
./gradlew build
pytest
npm test
npm run lint
~~~

최소 수집 정보:

- command
- exit code
- elapsed time
- 필요한 output

LLM은 실패 원인을 해석할 수 있지만 PASS / FAIL 자체를 대체하지 않습니다.

## 8. Bounded Repair

무제한 Agent loop를 허용하지 않습니다.

~~~text
Implement
   ↓
Validate
   ↓ FAIL
Repair
   ↓
Validate
   ↓ FAIL
Repair limit reached
   ↓
Stop + Report
~~~

최대 repair 횟수는 명시적으로 설정합니다.

## 9. Review Routing

Task signal을 기반으로 필요한 Review만 선택합니다.

예:

~~~text
database_change / transaction_change
    → database review

async / retry / idempotency / concurrency
    → reliability review
~~~

초기에는 독립 Review가 필요하면 DevFlow가 여러 `codex exec` CLI Worker를 실행해 결과를 취합할 수 있습니다. Native Subagent는 첫 구현의 필수 조건이 아닙니다.

## 10. Run Artifact

후보 구조:

~~~text
.codex-devflow/
  runs/
    <run-id>/
      task.json
      analysis.json
      plan.md
      validation.json
      review.json
      exec.md
      run.json
~~~

정확한 저장 위치는 구현 중 결정합니다.

## 11. Human Boundary

초기 버전에서 다음 고영향 동작은 사용자 명시적 행동 없이 수행하지 않습니다.

- push
- PR 생성
- merge
- branch 삭제
- destructive DB operation
