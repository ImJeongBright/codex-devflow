# 프로젝트 정의

## 1. 정체성

Codex DevFlow는 새로운 Coding Agent나 범용 Multi-Agent Framework를 만드는 프로젝트가 아닙니다.

**이미 사용하는 Codex를 더 일관되고 검증 가능하게 사용하는 local-first orchestration layer**입니다.

사용자가 반복적으로 수행하던 다음 개발 지휘를 하나의 재사용 가능한 workflow로 옮깁니다.

~~~text
Analyze → Plan → Implement → Validate → Review → Repair → Document
~~~

정체성, 기존 방식과의 차이, 기대효과에 대한 상세 설명은 [WHY.md](WHY.md)를 참고합니다.

## 2. 문제

Coding Agent는 이미 저장소 탐색, 계획, 구현, 리뷰를 수행할 수 있습니다.

실제 개발에서 반복되는 문제는 모델 능력보다 **그 능력을 매번 사람이 지휘해야 한다는 점**입니다.

~~~text
저장소 분석
→ 계획 작성
→ 구현
→ 테스트
→ diff 검토
→ 수정
→ 실행 기록
~~~

이 과정을 매 Task마다 다시 지시하면 다음 문제가 생깁니다.

- 반복적인 prompting
- Task마다 달라지는 개발 절차
- 어떤 단계에서 실패했는지 구분하기 어려움
- Skill, Review, Multi-Agent를 추가했을 때 실제 효과를 측정하기 어려움

## 3. 목표

Codex DevFlow는 큰 개발 요청 하나를 받아 반복 가능한 로컬 workflow로 변환합니다.

새로운 Foundation Model이나 범용 Agent Framework를 만드는 프로젝트가 아닙니다.

**이미 사용하는 Codex를 더 일관되고 검증 가능하게 사용하는 얇은 orchestration layer**를 만드는 프로젝트입니다.

## 4. 대표 사용 사례

입력:

~~~text
ImTicket에 메시지 버스 기반 비동기 후처리를 추가한다.
~~~

원하는 동작:

1. 현재 저장소를 탐색한다.
2. 변경 범위와 위험 요소를 구조화한다.
3. 적절한 workflow를 선택한다.
4. 필요한 경우 Plan을 만든다.
5. Plan 기준으로 구현한다.
6. deterministic validation을 실행한다.
7. 필요한 관점의 Review를 수행한다.
8. 실패하면 제한된 횟수만 Repair한다.
9. 실제 변경과 검증 결과를 Exec으로 남긴다.

사용자는 각 단계를 매번 직접 지시하지 않아야 합니다.

## 5. 핵심 가설

Workflow를 복잡하게 만들면 Codex 사용량과 elapsed time도 증가합니다.

따라서 다음을 가정하지 않고 검증합니다.

> 일정 수준 이상의 복잡한 개발 Task에서는 분석, 계획, deterministic validation, review를 분리한 workflow가 추가 사용량보다 더 큰 task success 또는 human rework 감소를 만든다.

반대로 단순 Task에서는 일반 Codex 실행이 더 효율적이라는 결과도 허용합니다.

## 6. 기대효과

다음은 구현 후 Eval로 확인할 가설입니다.

- 반복적인 후속 지시 감소
- 개발 절차의 일관성
- deterministic validation을 통한 검증 강화
- 실패 단계와 repair 이력 추적
- 실제 프로젝트에서 반복 사용 가능한 개인 개발 도구
- Task 복잡도에 따른 선택적인 orchestration

측정 없이 생산성이나 품질 향상을 확정적으로 주장하지 않습니다.

## 7. 제품 원칙

### Local First

첫 사용자는 프로젝트 개발자 본인입니다. 포트폴리오보다 실제 개발에서 먼저 쓸 수 있어야 합니다.

### 첫 버전은 직접 API 연동 없음

초기 backend는 ChatGPT 계정으로 로그인된 Codex CLI입니다.

DevFlow가 API Key나 모델 API client를 직접 관리하지 않습니다.

### 해석과 정책 분리

Codex:

- 영향 영역
- DB / transaction 관련 여부
- async / retry / idempotency 위험
- regression risk
- 필요한 review 관점

DevFlow:

- 어떤 workflow를 선택할지
- 어떤 command를 실행할지
- retry를 몇 번 허용할지
- 언제 중단할지
- artifact를 어디에 남길지

### Skill과 Workflow 분리

Skill은 특정 업무를 수행하는 방법을 제공합니다.

DevFlow는 Skill을 포함해 어떤 단계를 언제 실행하고 어떻게 연결할지 관리합니다.

### Multi-Agent는 필요할 때만

Subagent 수는 성과 지표가 아닙니다.

독립적인 review나 context isolation이 실제로 이득일 때만 추가합니다.

### Human Final Gate

초기 버전은 working tree를 수정하고 evidence를 만들 수 있지만 push / merge를 암묵적으로 수행하지 않습니다.

## 8. 성공 기준

- 하나의 명령으로 end-to-end workflow 시작
- Codex 분석 결과를 structured data로 획득
- deterministic validation 실행
- bounded repair
- Plan / Review / Exec artifact 저장
- run 단위 관측 데이터 확보
- 동일 Task로 direct Codex와 비교 가능
- 실제 개인 프로젝트 개발에서 반복 사용 가능

## 9. 초기 Non-goal

- Multi-LLM
- Remote SaaS
- Visual workflow editor
- 자동 production deploy
- 자동 merge 승인
- 범용 Agent Framework
- Agent 수 증가 자체
