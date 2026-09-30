# Roadmap

## 목적

이 문서는 Codex DevFlow가 첫 MVP 이후 어떤 순서로 발전할지 정의합니다.

Roadmap의 원칙은 기능을 많이 넣는 것이 아니라 **실제 사용과 Eval에서 다음 복잡성이 필요하다는 근거가 생겼을 때만 확장하는 것**입니다.

~~~text
001 MVP
  ↓
실제 사용
  ↓
문제 관찰
  ↓
측정
  ↓
다음 기능 추가
~~~

즉 각 단계는 이전 단계의 한계를 해결하기 위해 존재해야 합니다.

---

## Stage 0 — Single Workflow MVP

관련 문서:

- docs/plans/001-initial-implementation.md

목표:

> 하나의 개발 Task가 사람의 중간 지휘 없이 Analyze → Plan → Implement → Validate → Review → Record를 끝까지 통과할 수 있는가?

구현 범위:

- local CLI
- CodexCliBackend
- Repository Scout
- structured task analysis
- 최소 routing
- Plan artifact
- Implementation worker
- deterministic validation
- General Review worker
- bounded repair
- Run / Exec artifact

이 단계에서는 전문 Reviewer, 병렬 Worker, native Subagent를 넣지 않습니다.

### 완료 조건

실제 repository Task 하나 이상에서 다음이 생성되어야 합니다.

~~~text
task
analysis
plan
code change
validation evidence
review
repair history
final run record
~~~

### 다음 단계 진입 조건

다음 중 하나 이상을 실제 사용에서 확인합니다.

- 동일한 Review 기준을 반복해서 prompt에 넣고 있음
- DB / Reliability / Test처럼 반복 가능한 전문 검토 절차가 필요함
- General Reviewer가 지나치게 많은 책임을 가지고 있음
- Task 유형에 따른 Review 선택이 필요함

---

## Stage 1 — Reusable Skills

목표:

> 반복되는 engineering procedure를 prompt가 아니라 재사용 가능한 Skill로 분리한다.

후보 Skill:

~~~text
feature-planning
backend-review
database-review
reliability-review
test-review
execution-documentation
~~~

예:

database-review

- transaction boundary
- query path
- lock
- index 영향
- data consistency

reliability-review

- retry
- idempotency
- duplicate delivery
- failure / recovery

### 핵심 원칙

Skill은 workflow engine이 아닙니다.

~~~text
Skill
= 어떻게 수행할지

DevFlow
= 언제 실행할지, 어떤 순서로 연결할지
~~~

### 측정

- 동일 Review prompt 반복량
- Review finding quality
- false positive / false negative
- human rework
- Codex usage 변화

### 다음 단계 진입 조건

다음 중 하나 이상을 확인합니다.

- 모든 Task에 모든 Review Skill을 실행하면 overhead가 큼
- Task마다 필요한 Review 종류가 다름
- General Review보다 전문 Review가 실제 finding을 더 잘 발견함

---

## Stage 2 — Review Routing

목표:

> Task의 semantic signal을 기반으로 필요한 Review만 선택한다.

예:

~~~text
database_change / transaction_change
    → Database Review

async / retry / idempotency / concurrency
    → Reliability Review

test-heavy change
    → Test Review
~~~

Codex는 Task와 repository를 읽고 semantic signal을 반환합니다.

DevFlow는 해당 signal에 deterministic policy를 적용합니다.

~~~text
Codex
= 무엇이 관련되어 있는지 추론

DevFlow
= 어떤 workflow를 실행할지 결정
~~~

### 초기 형태

모든 역할은 native Subagent가 아니라 독립적인 CLI Worker로 실행할 수 있습니다.

~~~text
DevFlow
  |
  +-- codex exec → Planner
  +-- codex exec → Implementer
  +-- codex exec → Database Reviewer
  +-- codex exec → Reliability Reviewer
~~~

### 측정

- reviewer selection precision
- reviewer selection recall
- unnecessary review rate
- dangerous under-routing
- elapsed time
- Codex run count

### 다음 단계 진입 조건

다음 중 하나 이상을 확인합니다.

- 여러 독립 Review를 순차 실행하는 시간이 과도함
- Reviewer context를 분리할 실질적 이유가 있음
- 동일 diff를 읽는 여러 Review가 서로 독립적임

---

## Stage 3 — Parallel CLI Workers

목표:

> 서로 독립적인 읽기 중심 Review를 병렬 실행해 elapsed time을 줄인다.

초기 병렬화 대상:

~~~text
Database Review
Reliability Review
Test Review
~~~

초기에는 병렬 구현을 하지 않습니다.

~~~text
Implementation
→ 단일 Worker

Independent Review
→ 병렬 Worker 가능
~~~

이유:

- 동일 파일 동시 수정 충돌 방지
- merge orchestration 복잡도 회피
- 병렬화 효과를 Review 영역에서 먼저 검증

### 측정

- sequential review time
- parallel review time
- total Codex usage
- finding quality
- failure / timeout rate

### 다음 단계 진입 조건

병렬 CLI Worker가 실제 이점을 만들었지만 다음 한계가 확인될 때만 다음 단계로 갑니다.

- parent/worker 간 더 구조적인 delegation이 필요함
- worker 간 message passing이 필요함
- context lifecycle 관리가 CLI orchestration에서 과도하게 복잡함
- API 기반 실행의 추가 비용을 감수할 이유가 생김

---

## Stage 4 — Native Subagent 검토

목표:

> CLI Worker orchestration의 한계가 실제로 확인된 경우에만 native Subagent 또는 Agents API backend를 검토한다.

이 단계는 필수가 아닙니다.

현재 프로젝트의 핵심 가치는 native Subagent 사용 여부와 무관합니다.

검토 대상:

- parent agent delegation
- independent context lifecycle
- native handoff
- worker coordination
- hosted tracing

### 전환 판단

다음 질문에 YES가 있어야 합니다.

- CLI Worker로 구현하기 어려운 기능이 실제로 필요한가?
- API 비용보다 얻는 orchestration 이점이 큰가?
- 개인 local tool 범위를 넘어 remote / multi-user 실행이 필요한가?

그렇지 않다면 CodexCliBackend를 유지합니다.

---

## Stage 5 — Eval Harness

Eval은 마지막에 처음 도입하는 기능이 아니라 모든 단계에서 관측을 쌓고, 이 단계에서 **반복 가능한 benchmark harness**로 정식화합니다.

비교군:

~~~text
A. Direct Codex

B. Codex + Skill

C. Codex DevFlow
~~~

Task Set:

- 실제 완료한 repository Task
- small / medium / complex
- API
- validation
- transaction
- query / index
- retry / idempotency
- async / event-driven
- observability
- refactor

주요 지표:

- Task success
- Validation pass
- First-pass success
- Human rework
- Unrelated change
- Elapsed time
- Codex run count
- Repair attempts
- 사용 가능한 경우 Codex usage

목표:

> 어떤 Task에서 orchestration이 가치가 있고, 어디에서는 Direct Codex가 더 나은지 구분한다.

---

## Stage 6 — Policy Refinement

Eval 데이터가 쌓이면 routing policy를 수정합니다.

초기에는 단순한 rule로 시작합니다.

향후 후보:

~~~text
scope
database_change
transaction_change
async_processing
concurrency
retry_or_idempotency
migration
external_integration
regression_risk
~~~

중요한 점은 LLM에게 최종 policy까지 모두 맡기지 않는 것입니다.

~~~text
Codex
→ semantic signal

DevFlow
→ deterministic policy
~~~

실제 데이터에 따라 SIMPLE / MEDIUM / COMPLEX 구분 자체를 없애거나 다른 모델로 바꿀 수도 있습니다.

---

## Stage 7 — Real-world Dogfooding

목표:

> 포트폴리오용 benchmark가 아니라 실제 개발 도구로 지속 사용한다.

실제 프로젝트에서 다음을 관찰합니다.

- 어떤 workflow가 자주 사용되는가
- 사용자가 자주 override하는 단계는 무엇인가
- 어떤 Skill이 실제로 재사용되는가
- 어떤 Review가 noise를 많이 만드는가
- human review가 반드시 필요한 지점은 어디인가
- orchestration이 오히려 불편한 Task는 무엇인가

Dogfooding 결과는 다음 Plan의 입력이 됩니다.

~~~text
실사용
→ Run data
→ Eval
→ 의사결정
→ 다음 변경
~~~

---

## 장기 확장 후보

다음은 필요성이 검증되기 전까지 구현 계획이 아닙니다.

- GitHub Issue / PR integration
- CI integration
- project-specific workflow profile
- execution backend plugin
- remote execution
- API backend
- multi-user service
- alternative coding agent backend

---

## 하지 않을 것

Roadmap에서도 다음은 목표가 아닙니다.

- Agent 수 늘리기
- 프레임워크 사용 자체
- Multi-Agent라는 이름을 위한 복잡성
- 측정 없는 생산성 주장
- 무제한 autonomous loop
- 사용자의 승인 없이 destructive operation

---

## 전체 흐름

~~~text
001 Single Workflow MVP
        ↓
Reusable Skills
        ↓
Review Routing
        ↓
Parallel CLI Workers
        ↓
필요한 경우 Native Subagent 검토
        ↓
Eval Harness
        ↓
Policy Refinement
        ↓
Real-world Dogfooding
        ↓
반복
~~~

이 순서는 고정된 출시 일정이 아닙니다.

**이전 단계에서 다음 단계의 필요성을 실제로 확인했을 때만 진행합니다.**
