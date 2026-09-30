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

향후 독립 Review를 Subagent로 병렬 실행할 수 있지만, 첫 구현의 필수 조건은 아닙니다.

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
