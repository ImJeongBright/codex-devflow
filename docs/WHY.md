# 왜 Codex DevFlow인가

## 1. 정체성

Codex DevFlow는 새로운 Coding Agent를 만드는 프로젝트가 아닙니다.

**사용자가 Codex에게 반복적으로 수행하던 개발 지휘 과정을 재사용 가능한 workflow로 만들고, 그 효과를 실제 개발 Task로 검증하는 로컬 orchestration tool**입니다.

핵심 질문은 다음입니다.

> Codex가 이미 분석, 구현, 테스트, 리뷰를 할 수 있다면  
> 사람이 매번 그 순서를 직접 지시해야 하는가?

Codex DevFlow는 이 반복 지휘를 프로그램으로 옮깁니다.

~~~text
기존

사용자
  ↓
"저장소 분석해"
  ↓
"계획 작성해"
  ↓
"이제 구현해"
  ↓
"테스트해"
  ↓
"diff 리뷰해"
  ↓
"문제 수정해"
  ↓
"exec 문서 남겨"


DevFlow

사용자 Task
  ↓
Analyze
  ↓
Plan
  ↓
Implement
  ↓
Validate
  ↓
Review
  ↓
Repair
  ↓
Document
~~~

사용자는 목표, 제약, 완료 기준을 제공하고 DevFlow는 반복적인 실행 절차를 관리합니다.

---

## 2. 해결하려는 문제

Coding Agent의 능력이 부족해서 시작한 프로젝트가 아닙니다.

문제는 이미 충분히 강한 Agent를 실제 개발에서 사용할 때 다음 비용이 반복된다는 점입니다.

### 반복적인 지휘

기능 하나를 개발할 때마다 계획, 구현, 테스트, 리뷰, 기록을 다시 지시해야 합니다.

### Task마다 달라지는 절차

어떤 날은 Plan을 만들고, 어떤 날은 바로 구현합니다.  
Review나 문서화가 누락되기도 합니다.

### 실패 원인을 분리하기 어려움

한 번의 긴 Agent 실행 안에서 분석, 구현, 검증이 섞이면 무엇이 잘못됐는지 파악하기 어렵습니다.

### 과도한 Agent 사용

모든 Task에 Plan, Reviewer, Subagent를 붙이면 단순 작업까지 느리고 비싸집니다.

### 효과를 측정하기 어려움

Skill, Plan, Review, Multi-Agent를 추가했을 때 실제로 개발 결과가 좋아졌는지 확인할 기준이 필요합니다.

---

## 3. 기존 방식과 무엇이 다른가

| 방식 | 사용자가 관리하는 것 | 장점 | 한계 |
| --- | --- | --- | --- |
| Direct Codex | Task 지시와 후속 지휘 | 가장 단순하고 빠르게 시작 가능 | Plan, Test, Review, Document를 사람이 반복해서 이어줘야 할 수 있음 |
| Codex + Skill | Task와 전체 실행 흐름 | 반복 절차와 전문 지식 재사용 | Skill은 주로 "어떻게 할지"를 알려주며 workflow state 전체를 관리하지 않음 |
| Codex DevFlow | 목표, 제약, 완료 기준 | 분석부터 검증까지 workflow를 일관되게 실행하고 기록 | orchestration 자체의 시간과 Codex 사용량이 추가될 수 있음 |
| API 기반 Agent Application | 서비스 정책과 Agent 시스템 | 원격 서비스, 세밀한 제어, 다중 사용자 확장에 유리 | API Key, 별도 사용 비용, billing, SDK, rate limit 등의 운영 요소가 추가됨 |

Codex DevFlow의 초기 목적은 API 기반 Agent Platform을 대체하는 것이 아닙니다.

**개인 개발자가 이미 사용 중인 Codex CLI를 reasoning backend로 활용하면서, 별도의 모델 API client 없이 개발 workflow를 구조화하는 것**이 첫 목표입니다.

---

## 4. Skill과의 차이

Skill과 DevFlow는 경쟁 관계가 아닙니다.

### Skill

~~~text
"이 일을 어떻게 수행할 것인가?"
~~~

예:

- DB 변경을 리뷰할 때 transaction boundary를 확인한다.
- 메시징 변경에서는 retry, duplicate delivery, idempotency를 확인한다.
- 실행 문서는 계획 대비 실제 변경점을 구분해서 작성한다.

Skill은 **업무 지식과 절차**입니다.

### DevFlow

~~~text
"어떤 일을 언제 실행하고,
어떤 순서로 연결하며,
실패하면 어디로 돌아가고,
언제 종료할 것인가?"
~~~

DevFlow는 **workflow state와 orchestration policy**를 관리합니다.

~~~text
DevFlow
  |
  +-- Planning Skill
  +-- Database Review Skill
  +-- Reliability Review Skill
  +-- Documentation Skill
~~~

따라서 기존 Skill은 버리는 것이 아니라 DevFlow의 구성 요소가 됩니다.

---

## 5. Agent Framework와의 차이

Codex DevFlow는 범용 Multi-Agent Framework를 목표로 하지 않습니다.

다음 질문에 먼저 답합니다.

> 실제 소프트웨어 개발 Task에서 Agent를 더 많이 사용하는 것이 정말 더 좋은가?

따라서 초기 버전은 다음 순서로 발전합니다.

~~~text
Direct Codex
   ↓
Structured Workflow
   ↓
Skill
   ↓
Specialized Review
   ↓
필요한 경우에만 Subagent
~~~

Multi-Agent는 프로젝트의 정체성이 아니라 **Eval 결과에 따라 선택할 수 있는 구현 수단**입니다.

---

## 6. Codex CLI를 사용하는 이유

초기 DevFlow는 OpenAI API를 직접 호출하지 않습니다.

~~~text
DevFlow
   ↓
codex CLI / codex exec
   ↓
ChatGPT 계정으로 인증된 Codex
   ↓
OpenAI backend
~~~

DevFlow 관점에서는 Codex CLI가 reasoning executable 역할을 합니다.

이 구조의 의미는 다음과 같습니다.

- DevFlow 내부에 OpenAI API Key를 저장하지 않음
- 별도의 모델 API client를 구현하지 않음
- 개인 사용 단계에서 API 호출 비용 체계를 별도로 운영하지 않음
- 기존 ChatGPT 플랜의 Codex 사용량 체계를 그대로 활용
- 추론 backend와 workflow engine을 분리 가능

이것은 추론이 로컬에서 수행되거나 무료라는 뜻이 아닙니다.  
Codex는 OpenAI backend와 통신하며 사용자의 Codex allowance 또는 credit을 소비합니다.

핵심 차이는 **DevFlow가 직접 API billing client가 될 필요가 없다는 것**입니다.

---

## 7. 기대효과

다음은 현재 단계에서는 **검증할 가설**입니다. 구현 후 Eval을 통과하기 전까지 사실로 단정하지 않습니다.

### 반복 지시 감소

기존:

~~~text
Plan 작성
→ 구현
→ 테스트
→ 리뷰
→ Exec 작성
~~~

DevFlow:

~~~text
codex-devflow feature "<goal>"
~~~

하나의 Task에서 일련의 개발 workflow를 시작합니다.

### 개발 절차의 일관성

Task 유형과 위험 요소에 따라 필요한 단계가 반복 가능하게 적용됩니다.

예:

~~~text
단순 변경
→ Implement → Validate

DB / Transaction 변경
→ Plan → Implement → Validate → DB Review

Async / Retry / Idempotency 변경
→ Plan → Implement → Validate → Reliability Review
~~~

### 검증 가능성

Agent가 "완료했다"고 말하는 것과 실제 검증을 분리합니다.

~~~text
Build/Test/Lint
→ deterministic command

설계 적절성/위험 분석
→ Codex Review
~~~

### 실패 원인 추적

Plan, validation result, review finding, repair history를 Run artifact로 남깁니다.

실패했을 때 다음을 구분할 수 있습니다.

- Task 분석 오류
- Plan 오류
- Implementation 오류
- Validation 실패
- Review finding
- Repair 반복 실패

### 실제 개발에서 재사용

포트폴리오 데모를 위해 별도 문제를 만드는 대신 실제 프로젝트 개발에 계속 사용합니다.

DevFlow 자체의 개발 과정에서도 DevFlow의 workflow를 적용하는 dogfooding을 목표로 합니다.

### 선택적인 복잡성

모든 작업에 Multi-Agent를 강제하지 않습니다.

단순 Task에서는 orchestration overhead를 줄이고, 복잡한 Task에서만 더 강한 Plan/Review 경로를 사용합니다.

---

## 8. 무엇이 개선되면 성공인가

"Agent를 여러 개 만들었다"는 성공 기준이 아닙니다.

실제 Task에서 다음을 비교합니다.

~~~text
Direct Codex
vs
Codex + Skill
vs
Codex DevFlow
~~~

주요 지표:

- Task success
- Validation pass
- First-pass success
- Human rework
- Unrelated change
- Total elapsed time
- Codex run count
- Repair attempts
- 필요한 경우 Codex usage 정보

가능한 결과:

~~~text
Task success     증가
Human rework     감소
Elapsed time     증가
Codex usage      증가
~~~

이 경우도 실패가 아닙니다.

복잡한 Task에서는 추가 machine cost를 감수할 가치가 있는지 판단하면 됩니다.

반대로 단순 Task에서 품질 개선 없이 시간과 사용량만 증가한다면 해당 workflow를 SIMPLE path로 축소해야 합니다.

---

## 9. 포트폴리오에서 증명하려는 것

이 프로젝트가 증명하려는 것은 다음 문장이 아닙니다.

> Multi-Agent 시스템을 구축했다.

목표는 다음에 가깝습니다.

> 실제 개발 과정에서 반복되던 AI 지휘 절차를 Codex CLI 기반 workflow로 구조화하고, 의미 해석은 Codex에 맡기되 routing, validation, retry, artifact는 deterministic code로 통제했다. 이후 실제 개발 Task를 기준으로 Direct Codex, Skill, DevFlow를 비교해 품질, 재작업, 시간, 사용량의 trade-off를 검증했다.

즉 핵심 역량은 기술 이름 자체가 아니라 다음입니다.

- AI를 실제 개발 프로세스에 통합
- LLM과 deterministic software의 책임 분리
- workflow orchestration
- reusable Skill
- validation / bounded repair
- observability
- Eval 기반 의사결정

---

## 10. 한 문장 정의

> **Codex DevFlow는 Codex에게 반복적으로 내리던 개발 지휘를 코드화하고, 그 workflow가 실제로 더 나은 개발 결과를 만드는지 측정하는 local-first development orchestrator다.**
