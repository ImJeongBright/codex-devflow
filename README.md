# codex-devflow

> **Codex에게 반복적으로 내리던 개발 지휘를 코드화하고, 그 workflow가 실제로 더 나은 개발 결과를 만드는지 측정하는 local-first development orchestrator.**

Codex DevFlow는 **하나의 개발 요청을 분석 → 계획 → 구현 → 검증 → 리뷰 → 실행 기록으로 연결하는 로컬 개발 오케스트레이션 도구**입니다.

핵심은 새로운 LLM이나 범용 Agent Framework를 만드는 것이 아니라, 이미 사용 중인 Codex CLI를 실행 엔진으로 두고 반복적인 개발 지휘 과정을 프로그램으로 옮기는 것입니다.

## 정체성

Codex DevFlow가 관리하는 것은 모델 자체가 아니라 **개발 workflow**입니다.

~~~text
사용자
"기능을 만들어줘"
      ↓
Codex DevFlow
      ↓
Analyze → Plan → Implement → Validate → Review → Repair → Document
~~~

Skill은 "이 일을 어떻게 할지"를 제공하고, DevFlow는 "언제 어떤 일을 실행하고 실패 시 어디로 돌아갈지"를 관리합니다.

Multi-Agent는 목표가 아닙니다. 실제 Task에서 독립적인 review나 context isolation이 이득일 때만 사용합니다.

Planner / Implementer / Reviewer 역할 분리도 처음부터 native Subagent를 요구하지 않습니다. V1에서는 DevFlow가 필요한 역할마다 독립적인 `codex exec` CLI worker를 실행하고 결과를 취합합니다.

더 자세한 배경과 차별점은 [왜 Codex DevFlow인가](docs/WHY.md)를 참고합니다.

## 문제

현재 Coding Agent를 사용할 때 다음 지시를 반복하게 됩니다.

~~~text
저장소 분석해
→ 계획 문서 작성해
→ 계획대로 구현해
→ 테스트해
→ diff 검토해
→ 문제 있으면 수정해
→ 실제 변경 내용을 exec 문서로 남겨
~~~

Codex DevFlow는 이 과정을 하나의 재사용 가능한 workflow로 묶습니다.

~~~text
사용자 Task
    ↓
Codex Scout
    ↓
작업 특성 분석
    ↓
DevFlow Policy
    ↓
Plan
    ↓
Implement
    ↓
Build / Test
    ↓
Review
    ↓
Repair
    ↓
Exec
~~~

## 기존 방식과의 차이

| 방식 | 강점 | DevFlow와의 차이 |
| --- | --- | --- |
| Direct Codex | 가장 단순 | 후속 개발 절차를 사용자가 계속 지휘할 수 있음 |
| Codex + Skill | 반복 가능한 업무 절차 제공 | Skill 자체는 전체 workflow state를 관리하지 않음 |
| Codex DevFlow | workflow 실행, 검증, 기록을 통합 | orchestration overhead가 생길 수 있어 Eval 필요 |
| API 기반 Agent App | 원격 서비스와 세밀한 제어에 유리 | API Key, 별도 비용, billing/SDK 운영이 추가됨 |

## 기대효과

구현 전에는 가설이며 Eval로 검증합니다.

- 반복적인 Plan / Implement / Test / Review 지시 감소
- Task 유형에 따른 개발 절차 일관성
- build/test/lint를 통한 deterministic validation
- 실패 단계와 repair 이력 추적
- 실제 프로젝트에서 지속적으로 사용하는 local tool
- 단순 Task에는 가벼운 경로, 복잡한 Task에는 강한 검증 경로 선택

## 왜 Codex CLI인가

첫 구현에서는 OpenAI API를 직접 연동하지 않습니다.

ChatGPT 계정으로 로그인된 Codex CLI를 execution backend로 사용합니다. 따라서 DevFlow 자체가 API Key, 직접적인 API billing, 모델 SDK를 관리할 필요가 없습니다.

~~~text
DevFlow
  ↓
Codex CLI
  ↓
ChatGPT-authenticated Codex
  ↓
OpenAI backend
~~~

이것은 추론이 로컬이거나 무료라는 의미가 아닙니다. Codex 사용량은 사용자의 ChatGPT 플랜 allowance/credit을 소비합니다.

이 프로젝트에서 중요한 점은 **DevFlow가 별도의 LLM API client가 될 필요가 없다는 것**입니다.

## 설계 원칙

1. **한 번의 요청으로 개발 흐름을 시작한다.**
2. **LLM은 의미를 해석하고, 프로그램은 정책을 결정한다.**
3. **build/test/lint처럼 확정적으로 검사할 수 있는 것은 코드로 검증한다.**
4. **Skill은 반복 가능한 업무 절차를 제공하고, workflow state는 DevFlow가 관리한다.**
5. **단순 작업에 복잡한 orchestration을 강제하지 않는다.**
6. **Multi-Agent는 목표가 아니라 필요할 때 선택하는 수단이다.**
7. **효과는 Eval로 검증한 뒤 주장한다.**

## 목표 구조

~~~text
User Task
    |
    v
Codex Scout / Classifier
    |
    | structured signals
    v
DevFlow Policy Engine
    |
    +------------+-------------+
    |            |             |
  SIMPLE       MEDIUM        COMPLEX
    |            |             |
 Implement      Plan          Plan
 Validate       Implement     Implement
 Finish         Validate      Validate
                Review        Specialized Review
                Finish        Bounded Repair
                              Exec
~~~

초기의 SIMPLE / MEDIUM / COMPLEX 경계는 확정하지 않습니다. 실제 Task와 Eval 결과를 기반으로 조정합니다.

## 첫 번째 범위

포함:

- 로컬 CLI
- Codex CLI execution backend
- 저장소 기반 Task 분석
- structured output
- deterministic workflow routing
- Plan / Exec artifact
- build / test / lint 실행
- bounded repair
- run log / metric
- 향후 Skill 및 Subagent 확장 가능 구조

포함하지 않음:

- SaaS
- OpenAI API 직접 연동
- Multi-LLM 지원
- 자동 merge
- 무제한 Agent loop
- Multi-Agent 자체를 위한 Multi-Agent

## 예상 사용 형태

~~~bash
codex-devflow feature "ImTicket에 메시지 버스 기반 비동기 후처리를 추가"
~~~

명령 이름과 구현 언어는 첫 구현 과정에서 확정합니다.

## 평가

DevFlow가 더 복잡하다는 이유만으로 더 좋다고 가정하지 않습니다.

~~~text
Direct Codex
vs
Codex + Skill
vs
Codex DevFlow
~~~

동일한 실제 개발 Task에서 Task success, first-pass success, human rework, elapsed time, Codex usage 등의 trade-off를 비교합니다.

## 문서

- [왜 Codex DevFlow인가](docs/WHY.md)
- [프로젝트 정의](docs/PROJECT.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [평가 전략](docs/EVALUATION.md)
- [Roadmap](docs/ROADMAP.md)
- [첫 번째 구현 계획](docs/plans/001-initial-implementation.md)
- [공식 레퍼런스](docs/REFERENCES.md)

## 현재 상태

설계 및 첫 구현 준비 단계입니다.

첫 목표는 거대한 Multi-Agent Framework가 아닙니다.

~~~text
Analyze → Plan → Implement → Validate → Review → Document
~~~

이 흐름을 실제 저장소 Task 하나에서 끝까지 실행하고, 기존 Codex 사용 방식보다 무엇이 좋아지고 무엇이 비싸지는지 측정할 수 있는 상태까지 만드는 것이 첫 목표입니다.

## License

MIT License.
