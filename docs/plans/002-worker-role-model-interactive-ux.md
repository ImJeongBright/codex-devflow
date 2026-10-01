# 002 — Worker Role, Model Policy, Interactive UX

## 목적

001에서 Codex DevFlow는 하나의 Task를 받아 Analyze → Plan → Implement → Validate → Review → Repair → Record를 수행하는 최소 workflow를 만들었다.

다음 단계에서는 기능을 늘리기 전에 **각 Codex 실행의 역할과 실행 조건을 명시적인 계약으로 고정하고, 사용자가 복잡한 CLI 옵션을 외우지 않아도 DevFlow를 사용할 수 있는 입력 구조**를 만든다.

이번 계획의 핵심은 세 가지다.

1. Core Worker Role을 확정한다.
2. Role별 기본 model / reasoning policy를 정의하고 사용자가 override할 수 있게 한다.
3. `codex-devflow feature` 하나만 입력해도 Task와 설정을 선택할 수 있는 interactive terminal UX를 제공한다.

이 단계는 전문 Reviewer, 병렬 Worker, native Subagent를 추가하는 단계가 아니다.

---

## 문제

### 실행 역할이 암묵적이다

001에서는 Scout, Planner, Implementer, Reviewer, Repairer에 해당하는 Codex 실행이 존재하지만, 실행 기록의 공통 identity로 Role이 명시적으로 관리되지 않는다.

이 상태에서는 다음을 정확하게 비교하기 어렵다.

- 어떤 Role이 어떤 모델을 사용했는가
- 어떤 Role에서 latency / usage가 증가했는가
- Planner의 강한 모델 사용이 실제로 효과가 있었는가
- Reviewer나 Repairer에 더 강한 모델이 필요한가

### Codex CLI 기본 모델에 의존하면 Eval 재현성이 떨어진다

DevFlow가 model과 reasoning effort를 명시하지 않으면 로컬 Codex 설정 또는 향후 기본값 변화에 따라 실행 조건이 달라질 수 있다.

동일 Task를 Direct Codex / Skill / DevFlow로 비교하려면 실행 조건을 artifact에 남겨야 한다.

### CLI 옵션이 많아지면 사용 부담이 커진다

Role별 모델, reasoning, repository, validation 등의 옵션을 모두 command argument로 노출하면 사용자가 DevFlow를 쓰기 위해 DevFlow 자체를 공부해야 한다.

DevFlow의 목적은 AI 지휘에 필요한 반복 입력을 줄이는 것이므로 기본 사용 경로 역시 최소 입력이어야 한다.

---

## 사용자 경험 원칙

기본 사용자는 다음 명령 하나만 기억하면 된다.

~~~bash
.venv/bin/codex-devflow feature
~~~

Task argument가 없고 interactive terminal이라면 DevFlow가 terminal UI를 연다.

예상 흐름:

~~~text
┌─ Codex DevFlow ──────────────────────────────┐
│                                              │
│ Repository                                   │
│ ✓ /Users/.../ImTicket                        │
│                                              │
│ What do you want to build?                   │
│ ┌──────────────────────────────────────────┐ │
│ │ 결제 완료 후 후처리를 비동기로 전환한다 │ │
│ │                                          │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│ Worker policy                                │
│ ● Recommended defaults                      │
│ ○ Customize roles                           │
│                                              │
│                 [ Run ]                      │
└──────────────────────────────────────────────┘
~~~

평소에는 Task만 입력하고 실행한다.

모델을 직접 조정하려는 사용자만 `Customize roles`를 연다.

---

## Core Role 계약

이번 단계에서 Core Role 이름을 다음 다섯 개로 고정한다.

### scout

책임:

- target repository 탐색
- Task 해석
- semantic signal 생성
- 위험 요소와 영향 범위 추론

권한:

- read-only

코드 수정:

- 금지

### planner

책임:

- Task와 Scout 결과를 기반으로 Plan 생성
- 구현 순서, validation, risk 정의

권한:

- read-only

코드 수정:

- 금지

### implementer

책임:

- Task와 Plan에 따라 working tree 수정
- 실제 구현 결과 structured output 생성

권한:

- workspace-write

코드 수정:

- 허용

### reviewer

책임:

- original task
- plan
- git diff
- validation evidence

를 기준으로 General Review 수행

권한:

- read-only

코드 수정:

- 금지

### repairer

책임:

- validation failure 또는 review finding을 기반으로 제한된 수정
- 기존 bounded repair policy 준수

권한:

- workspace-write

코드 수정:

- 허용

---

## Role과 다른 개념의 구분

~~~text
Role
= 누가 어떤 책임을 맡는가

Model Policy
= 해당 Role이 어떤 model / reasoning으로 실행되는가

Skill
= 해당 Role이 일을 어떻게 수행하는가

CLI Worker
= DevFlow가 Role을 수행하도록 실행한 독립 codex exec process

Native Subagent
= Agent runtime 내부에서 parent가 spawn / delegate하는 별도 agent
~~~

이번 단계에서는 Role + Model Policy + CLI Worker까지만 다룬다.

Skill, specialized Role, native Subagent는 Roadmap의 후속 단계에서 다룬다.

---

## 기본 Model Policy

Built-in recommended policy:

| Role | Model | Reasoning effort |
| --- | --- | --- |
| scout | `gpt-6-luna` | `max` |
| planner | `gpt-6.1-sol` | `high` |
| implementer | `gpt-6-luna` | `max` |
| reviewer | `gpt-6-luna` | `max` |
| repairer | `gpt-6-luna` | `max` |

설계 의도:

- Planner의 판단 오류는 이후 구현 전체에 영향을 주므로 기본적으로 더 강한 모델을 사용한다.
- 나머지 Role은 Task 또는 Plan으로 범위가 더 제한된 실행이므로 Luna를 기본 worker로 사용한다.
- 이 정책은 최종 정답이 아니라 Eval을 위한 초기 baseline이다.
- 향후 데이터에서 특정 Role이 반복적으로 실패하면 해당 Role만 model / reasoning을 조정한다.

모델이 제공되지 않거나 선택한 reasoning effort가 지원되지 않는 경우 **조용히 다른 모델로 fallback하지 않는다.**

재현성을 위해 실행을 실패시키고 사용자가 원인을 확인할 수 있게 한다.

---

## Interactive Role Customization

`Customize roles`를 선택하면 다음과 같은 설정 화면을 제공한다.

~~~text
Worker Configuration

Scout
  Model      [ GPT-6 Luna      ▼ ]
  Reasoning  [ Max             ▼ ]

Planner
  Model      [ GPT-6.1 Sol     ▼ ]
  Reasoning  [ High            ▼ ]

Implementer
  Model      [ GPT-6 Luna      ▼ ]
  Reasoning  [ Max             ▼ ]

Reviewer
  Model      [ GPT-6 Luna      ▼ ]
  Reasoning  [ Max             ▼ ]

Repairer
  Model      [ GPT-6 Luna      ▼ ]
  Reasoning  [ Max             ▼ ]

[ Run only ]  [ Save project default ]  [ Run ]
~~~

초기 model selector는 DevFlow가 알고 있는 preset을 보여주되, 향후 모델 변화에 대응할 수 있도록 custom model ID 입력 경로를 열어둔다.

model catalog를 완전히 자동 탐색하는 기능은 이번 단계의 완료 조건이 아니다.

---

## 실행 중 UX

사용자는 DevFlow가 현재 어느 단계인지 확인할 수 있어야 한다.

~~~text
Codex DevFlow

✓ Scout
  gpt-6-luna / max
  11.8s

✓ Planner
  gpt-6.1-sol / high
  23.4s

● Implementer
  gpt-6-luna / max
  running...

○ Validation
○ Reviewer
○ Finalize
~~~

Validation 실패 시:

~~~text
✗ Validation

python3 -m unittest discover -s tests -v
exit code: 1

2 tests failed

→ Repairer 1/2
~~~

완료 시:

~~~text
✓ DevFlow completed

Changed files       3
Validation           Passed
Review               Passed
Repair attempts      1
Elapsed              3m 14s

Exec
.codex-devflow/runs/<run-id>/exec.md
~~~

화려한 animation보다 **현재 Role, model, reasoning, stage, failure reason을 명확하게 보여주는 것**을 우선한다.

---

## CLI / Interactive Mode 공존

Interactive UX를 추가해도 기존 CLI 실행을 제거하지 않는다.

### Interactive

~~~bash
codex-devflow feature
~~~

Task argument가 없고 stdin/stdout이 TTY인 경우 interactive mode를 연다.

### Direct CLI

~~~bash
codex-devflow feature "메시지 버스 기반 비동기 후처리를 추가"
~~~

기존처럼 바로 workflow를 시작한다.

### Advanced override

자동화 또는 숙련 사용자를 위해 Role override를 지원한다.

후보 문법:

~~~bash
codex-devflow feature "메시지 버스 추가" \
  --role-model planner=gpt-6.1-sol \
  --role-reasoning planner=high \
  --role-model implementer=gpt-6-luna \
  --role-reasoning implementer=max
~~~

정확한 argument naming은 구현 과정에서 기존 CLI 구조와 충돌이 없는 형태로 확정한다.

### Non-interactive safety

TTY가 아닌 환경에서 Task가 비어 있으면 prompt를 기다리며 hang하지 않는다.

명확한 usage error로 종료한다.

CI / script에서 interactive prompt가 암묵적으로 열리지 않아야 한다.

---

## 설정 우선순위

설정은 다음 순서로 병합한다.

~~~text
Built-in defaults
        ↓
User global config
        ↓
Repository config
        ↓
Interactive run selection / CLI override
~~~

아래로 갈수록 우선순위가 높다.

최종 effective policy는 worker 실행 전에 계산하고 artifact에 기록한다.

### Built-in

DevFlow가 제공하는 recommended Role policy.

### Global

사용자의 반복 선호를 저장한다.

정확한 platform path는 구현 시 결정하되 repository 밖의 사용자 설정으로 관리한다.

### Repository

현재 `.codex-devflow.json`을 확장해 프로젝트별 Role policy를 저장한다.

후보:

~~~json
{
  "roles": {
    "planner": {
      "model": "gpt-6.1-sol",
      "reasoning_effort": "high"
    },
    "implementer": {
      "model": "gpt-6-luna",
      "reasoning_effort": "max"
    }
  }
}
~~~

기존 001 설정과 backward compatible해야 한다.

### Run override

Interactive 화면 또는 CLI option으로 이번 실행에만 적용한다.

---

## Codex CLI 실행

CodexCliBackend는 Role 실행 시 effective policy를 명시적으로 Codex CLI에 전달한다.

개념:

~~~bash
codex exec \
  --model gpt-6.1-sol \
  --config 'model_reasoning_effort="high"' \
  ...
~~~

Backend 호출 인터페이스는 최소한 다음 정보를 받아야 한다.

~~~text
role
model
reasoning_effort
sandbox
working_directory
prompt
output_schema
~~~

Role이 직접 process command를 조합하지 않는다.

모든 실행은 CodexCliBackend를 통과한다.

---

## Run Artifact 확장

Eval 재현성을 위해 각 Codex 실행에 실제 effective policy를 기록한다.

후보:

~~~json
{
  "workers": [
    {
      "sequence": 1,
      "role": "scout",
      "model": "gpt-6-luna",
      "reasoning_effort": "max",
      "sandbox": "read-only",
      "elapsed_seconds": 11.8,
      "exit_code": 0,
      "usage": {}
    },
    {
      "sequence": 2,
      "role": "planner",
      "model": "gpt-6.1-sol",
      "reasoning_effort": "high",
      "sandbox": "read-only",
      "elapsed_seconds": 23.4,
      "exit_code": 0,
      "usage": {}
    }
  ]
}
~~~

최소 기록:

- role
- model
- reasoning effort
- sandbox / permission profile
- started / completed 상태
- elapsed time
- exit / timeout / interruption
- 수집 가능한 usage

기존 raw usage를 제거하지 않는다.

기존 artifact와 호환 가능한 방식으로 schema를 확장한다.

Simple workflow에서 실행되지 않은 Role을 실행된 것처럼 기록하지 않는다.

---

## 구현 순서

### 1. Role type 도입

Core Role 다섯 개를 코드의 공통 vocabulary로 만든다.

string literal이 여러 파일에 흩어지지 않게 한다.

### 2. Role Policy model

Role별 model / reasoning / permission을 표현하는 구조를 만든다.

Built-in recommended defaults를 정의한다.

### 3. Config merge

Built-in → global → repository → run override 순서의 effective policy 계산을 구현한다.

기존 config를 깨지 않는다.

### 4. Backend 전달

모든 Codex worker가 자신의 Role policy를 CodexCliBackend에 전달하도록 변경한다.

실제 `codex exec` command에 model과 reasoning effort를 명시한다.

### 5. Artifact 확장

worker identity와 실제 effective policy를 run artifact에 기록한다.

실패 / timeout / interruption에서도 실행 조건이 남아야 한다.

### 6. Interactive input layer

Task argument가 없고 TTY인 경우 interactive mode를 연다.

최소 화면:

- repository 확인
- multi-line 또는 충분한 길이의 Task 입력
- recommended defaults / customize 선택
- Role model / reasoning 선택
- 실행 확인

### 7. Live progress

현재 workflow stage와 Role 상태를 terminal에 표시한다.

기존 artifact / log 생성 로직이 UI에 종속되지 않게 한다.

### 8. Direct CLI compatibility

Task argument를 직접 전달하는 기존 사용법과 tests를 유지한다.

### 9. Verification

실제 Codex CLI run에서 Planner와 나머지 worker가 서로 다른 model policy로 실행되는지 확인한다.

---

## TUI 구현 원칙

이번 단계는 **terminal interactive UX**를 만든다.

별도 desktop GUI window는 만들지 않는다.

이유:

- DevFlow는 local developer tool이다.
- SSH / remote shell / terminal workflow와 자연스럽게 호환된다.
- desktop packaging과 window lifecycle 복잡성을 피한다.
- 기존 CLI automation path를 그대로 유지할 수 있다.

구현 library는 목표가 아니다.

가능하면 의존성을 최소화하되, arrow selection / multi-line input / testability를 위해 작은 TUI dependency가 실제로 필요하면 도입 근거를 Exec에 기록한다.

UI library가 workflow engine에 침투하지 않도록 input/output adapter 경계를 둔다.

---

## 테스트

최소 다음을 자동 검증한다.

### Role

- Core Role 다섯 개만 기본 workflow에서 사용
- 각 Role의 read-only / workspace-write 경계
- Simple path에서 planner/reviewer가 생략될 경우 실행 record도 생성되지 않음

### Default policy

- scout = `gpt-6-luna / max`
- planner = `gpt-6.1-sol / high`
- implementer = `gpt-6-luna / max`
- reviewer = `gpt-6-luna / max`
- repairer = `gpt-6-luna / max`

### Override

- repository config가 built-in을 덮음
- global config가 built-in을 덮음
- repository가 global보다 우선
- CLI / interactive selection이 최종 우선
- 한 Role override가 다른 Role policy를 변경하지 않음

### Backend

- Role별 `--model` 전달
- Role별 `model_reasoning_effort` 전달
- invalid configuration 처리
- unavailable model / unsupported effort에서 silent fallback 없음

### Artifact

- role/model/reasoning이 실제 worker execution과 일치
- 성공 / error / timeout / interruption 모두 policy evidence 보존
- usage가 어떤 Role 실행에서 발생했는지 연결 가능

### Interactive

- no task + TTY → interactive
- task argument 존재 → direct
- no task + non-TTY → usage error
- default 선택 시 추가 model 입력 없이 실행 가능
- customize에서 Role별 선택 가능
- cancel 시 Codex worker를 시작하지 않음

### Regression

001의 기존 workflow / validation / bounded repair / signal handling / run lock / artifact tests가 계속 통과해야 한다.

---

## 실제 검증 시나리오

### Scenario A — 기본 사용

~~~bash
.venv/bin/codex-devflow feature
~~~

사용자는 Task만 입력하고 recommended defaults로 실행한다.

확인:

- Planner는 `gpt-6.1-sol / high`
- 나머지 실행된 Role은 `gpt-6-luna / max`
- run artifact에 실제 policy가 기록됨

### Scenario B — 사용자 선택

Interactive customization에서 reviewer만 다른 model / effort로 변경한다.

확인:

- reviewer만 override
- 다른 Role은 default 유지
- artifact가 override를 반영

### Scenario C — Direct CLI

기존 방식으로 Task를 argument로 전달한다.

확인:

- TUI가 열리지 않음
- default policy로 workflow 실행
- 기존 automation compatibility 유지

### Scenario D — 잘못된 모델 설정

존재하지 않는 model ID 또는 지원되지 않는 effort를 지정한다.

확인:

- 다른 모델로 자동 fallback하지 않음
- worker failure evidence와 원인이 보존됨

---

## 관측 지표

이번 단계부터 Role 단위로 다음을 수집할 수 있게 한다.

- run count
- elapsed
- input / cached input / output / reasoning usage
- exit / timeout / interruption
- validation outcome과의 관계
- repair 진입 여부

이 정보는 향후 다음 질문에 답하기 위한 기반이다.

~~~text
Planner를 Sol high로 사용하는 것이 실제 결과를 개선하는가?

Implementer도 Sol로 승격할 필요가 있는가?

Reviewer는 Luna max로 충분한가?

Role별 model 차이가 elapsed / usage / human rework에 어떤 영향을 주는가?
~~~

이번 계획에서는 이 질문의 결론을 내리지 않는다.

측정 가능한 실행 조건을 만드는 것이 목표다.

---

## Non-goal

이번 002에 포함하지 않는다.

- specialized reviewer Role
- database / reliability / test Skill
- parallel worker
- native Subagent
- Agents API
- Multi-LLM backend
- desktop GUI
- workflow visual editor
- 자동 push / merge
- model quality ranking
- 복잡도에 따른 자동 model 승격

---

## Definition of Done

다음이 모두 충족되면 002를 완료한다.

1. Core Role `scout / planner / implementer / reviewer / repairer`가 코드와 artifact의 공통 identity로 사용된다.
2. 각 Role에 explicit model / reasoning policy가 존재한다.
3. 기본 policy가 Planner = `gpt-6.1-sol / high`, 나머지 = `gpt-6-luna / max`로 동작한다.
4. 사용자가 Role별 model / reasoning을 override할 수 있다.
5. `codex-devflow feature`만 실행하면 interactive terminal flow가 열린다.
6. 기본 사용에서는 Task 외 추가 설정 입력을 요구하지 않는다.
7. 기존 `codex-devflow feature "<task>"` direct mode가 유지된다.
8. non-TTY 환경에서 implicit interactive hang이 발생하지 않는다.
9. worker별 role/model/reasoning/elapsed/result/usage가 run artifact에 연결된다.
10. unavailable model 또는 invalid effort에서 silent fallback하지 않는다.
11. 기존 001 regression tests가 유지되고 신규 tests가 통과한다.
12. 실제 로그인된 Codex CLI로 최소 한 번 end-to-end run을 수행하고 Role별 effective policy evidence를 남긴다.
13. 완료 후 `docs/exec/002-worker-role-model-interactive-ux.md`에 실제 구현, 계획 대비 변경, 검증, 한계를 기록한다.

---

## 이후

002 완료 후에는 바로 전문 Reviewer를 추가하지 않는다.

먼저 실제 프로젝트에서 interactive UX와 Role policy를 사용하며 run evidence를 축적한다.

기존 001 실행에서 발견된 runtime error 원인 전달 문제는 별도 후속 Plan으로 다룬다.

그 다음 실제 사용에서 반복되는 검토 절차가 확인되면 Roadmap의 Reusable Skills / Review Routing으로 진행한다.
