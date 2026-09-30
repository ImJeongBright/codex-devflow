# 첫 번째 구현 계획

## 목적

실제 개발에 사용할 수 있으면서 다음 개선을 판단할 데이터를 남기는 **가장 작은 Codex DevFlow**를 구현합니다.

첫 구현부터 Multi-Agent를 만들지 않습니다.

## 완료 상태

개발자가 하나의 Task를 입력했을 때 DevFlow가 다음을 수행할 수 있어야 합니다.

1. 로그인된 Codex CLI 실행
2. target repository 탐색 요청
3. structured task analysis 획득
4. 필요한 workflow 선택
5. Plan 생성
6. Plan 기반 구현
7. deterministic validation
8. general review
9. 제한된 repair
10. run artifact 기록

## 첫 번째 실행

### 1. CLI Skeleton

최소한의 local command를 만듭니다.

후보:

~~~bash
codex-devflow feature "<task>"
~~~

처음에는 target repository path와 task text 정도만 받습니다.

구현 언어와 최종 binary name은 이 단계에서 결정합니다.

### 2. Codex CLI Backend

Codex 실행을 내부 abstraction 뒤에 둡니다.

책임:

- target repository에서 Codex 실행
- prompt 전달
- process exit status 수집
- output 수집
- structured JSON 결과 지원
- timeout
- normalized internal result 반환

이 단계에서는 OpenAI API client를 추가하지 않습니다.

### 3. Repository Scout

Codex가 코드를 수정하지 않고 repository를 탐색합니다.

초기 structured signal 후보:

- 영향 영역
- DB 변경
- transaction 변경
- async
- concurrency
- retry / idempotency
- migration
- external integration
- regression risk
- suggested review

Schema에는 version을 둡니다.

### 4. 초기 Policy Engine

처음부터 완벽한 난이도 점수를 만들지 않습니다.

최소한 다음 두 경로부터 검증할 수 있습니다.

~~~text
명확한 local / low-risk 변경
    → Implement + Validate

그 외
    → Plan + Implement + Validate + General Review
~~~

실제 Run을 모은 뒤 routing을 세분화합니다.

### 5. Plan Artifact

Planned workflow에서는 Codex가 다음을 포함한 Plan을 생성합니다.

- 문제
- 현재 동작
- 목표
- 예상 영향 파일 / 컴포넌트
- 구현 순서
- validation
- risk

먼저 run artifact로 저장합니다.

Target repository에 Plan을 영구 보관할지는 나중에 옵션으로 결정합니다.

### 6. Implementation

원 Task와 Plan을 Codex에 제공하고 working tree 변경을 허용합니다.

Implementation step 자체가 validation 성공을 선언하지 않습니다.

### 7. Deterministic Validation

프로젝트별 shell command 목록을 지원합니다.

수집:

- command
- exit code
- elapsed time
- 필요한 stdout / stderr

Validation 설정이 없다면 verified라고 표시하지 않고 validation unavailable 상태를 남깁니다.

### 8. General Review

다음을 Codex에 제공합니다.

- original task
- plan
- git diff
- validation result

Structured review 최소 필드:

- pass / fail
- finding
- severity
- repair recommendation

### 9. Bounded Repair

Validation 또는 Review 실패 시 명시적인 최대 횟수까지만 Repair합니다.

한도를 넘으면 자동 반복을 멈추고 evidence를 사용자에게 반환합니다.

### 10. Exec Artifact

Run 종료 시 다음을 기록합니다.

- task
- analysis
- selected workflow
- plan
- actual changed files
- validation
- review
- repair history
- plan 대비 변경점
- unresolved limitation
- elapsed time
- 수집 가능한 Codex usage 정보

## 두 번째 실행

첫 번째 end-to-end가 실제 저장소에서 동작한 뒤 진행합니다.

- reusable Skill 추가
- database / reliability / test review procedure
- specialized review routing
- 실제 Run 데이터 기반 policy 수정
- metric 확장

Skill은 workflow engine을 대체하지 않고 반복 가능한 engineering procedure를 정의합니다.

## 세 번째 실행

독립 context 또는 병렬 처리가 실제로 필요하다는 근거가 생긴 뒤 진행합니다.

- Codex Subagent 도입
- 독립 Review 병렬화
- usage / latency 증가 측정
- 실제 outcome을 개선한 Subagent만 유지

## 네 번째 실행

반복 가능한 Eval Harness를 만듭니다.

~~~text
Direct Codex
Codex + Skill
Codex DevFlow
~~~

실제 프로젝트 Task를 동일 조건으로 실행하고 docs/EVALUATION.md 지표를 기록합니다.

## 현재 미확정

구현 전에 억지로 확정하지 않습니다.

- implementation language
- 최종 CLI 이름
- task analysis schema 세부
- complexity threshold
- run artifact 위치
- target repository의 Plan / Exec commit 여부
- Codex usage 측정 방식
- 어떤 specialized review가 실제 이득인지

## 이 계획의 Definition of Done

실제 저장소의 Task 하나에서 다음 artifact가 모두 생성되고 검증되면 첫 번째 계획을 완료합니다.

~~~text
task
analysis
plan
code change
validation evidence
review
final run record
~~~

완료 후 docs/exec 아래에 첫 실행 문서를 작성하고, 실제로 발견한 문제를 근거로 다음 계획을 만듭니다.
