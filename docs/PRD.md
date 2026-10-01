# Codex DevFlow V0 PRD

## 목적과 사용자

개발자가 로컬 Git 저장소와 개발 요청 하나를 전달하면 Codex CLI를 통해 분석부터 실행 기록까지 진행한다. 요구사항의 근거는 `PROJECT.md`와 `plans/001-initial-implementation.md`다. 이 문서는 001의 범위를 구체화한다.

## 현재 상태와 문제

001 계획 작성 당시 저장소에는 설계 문서만 있었다. 사용자는 분석, 계획, 구현, 검증, 리뷰, 수정, 기록을 매번 지시해야 했다. V0는 이 절차와 중단 조건을 코드로 관리한다.

## 기능 요구사항

| ID | 요구사항 | 수용 조건 |
| --- | --- | --- |
| R1 | 로컬 CLI | task와 repository를 받아 한 번의 명령으로 실행한다. |
| R2 | Codex backend | 로그인된 CLI를 target에서 실행하며 stdout/stderr, exit code, timeout, structured output을 수집한다. |
| R3 | Scout | 읽기 전용으로 저장소를 분석하고 version이 있는 JSON을 검증한다. |
| R4 | Routing | local/low risk이고 위험 신호가 모두 false인 경우 simple, 나머지는 planned로 결정한다. |
| R5 | Plan/Implement | planned 경로에서 문제·현재 동작·목표·영향·순서·검증·위험을 기록하고 원 task와 함께 구현에 전달한다. |
| R6 | Validation | 사용자가 설정한 shell 명령 목록을 target에서 실행하고 각각의 종료 코드·시간·출력을 저장한다. 미설정 시 unavailable이며 verified로 표시하지 않는다. |
| R7 | General review | planned 경로에서 task·plan·diff·validation을 제공하고 pass/fail, finding, severity, repair recommendation을 검증한다. |
| R8 | Repair | validation 또는 review 실패 시 설정한 한도만큼 수정하고 다시 검증한다. planned 경로는 다시 리뷰한다. |
| R9 | Evidence | 성공·실패·timeout·중단 시 task, analysis, workflow, plan, changed files, validation, review, repair, 계획 대비 변경점, 제한, elapsed, 노출된 usage를 저장한다. 실행되지 않은 단계는 명시한다. |
| R10 | Human boundary | push/PR/merge/branch 삭제/파괴적 DB 작업을 workflow에 추가하지 않는다. Codex에도 금지를 전달하고 sandbox를 유지한다. |

## 인터페이스와 상태

- Python 3.11+와 POSIX 환경, Git, 로그인된 Codex CLI를 사용한다.
- `codex-devflow feature "<task>" --repo <path>`; 설치 없이 `python3 -m codex_devflow`도 지원한다.
- validation은 반복 가능한 `--validate` 또는 target의 `.codex-devflow.json`으로 설정한다.
- timeout과 최대 repair는 양의 timeout, 0 이상의 repair 횟수로 제한한다.
- artifact는 target의 `.codex-devflow/runs/<run-id>/`에 저장한다.
- 종료 상태는 `succeeded`, `unverified`, `failed`, `error`, `interrupted`로 구분한다. CLI 성공 코드는 검증된 성공만 0이다.
- 변경 파일은 시작 전 snapshot과 종료 상태를 비교한다. 기존 working tree 변경은 별도로 기록하고 자동 정리하지 않는다.

## 범위 밖

전문 reviewer, 병렬 worker, native subagent, API backend, skill 시스템, eval harness, 자동 push/merge, 원격 서비스는 후속 단계다.

## 검증과 완료 조건

단위·통합 테스트로 schema, routing, process timeout, validation, repair 상한, 실패 기록을 확인한다. 실제 로그인된 Codex CLI로 Git 저장소 task를 수행해 task/analysis/plan/code change/validation/review/final run record를 확인한다. 외부 실행이 막히면 성공으로 간주하지 않고 해당 DoD를 미충족으로 기록한다.

## 위험과 제한

Codex 결과와 시간은 비결정적이다. sandbox와 prompt는 악의적인 명령에 대한 완전한 권한 시스템이 아니다. validation은 사용자가 신뢰하는 명령을 직접 실행한다. V0는 한 저장소에 한 run만 수행하며 resume, 강제 종료 후 복구, 비용 추정은 제공하지 않는다.

## 002 추가 요구사항

근거: [002 계획](plans/002-worker-role-model-interactive-ux.md).

- Core identity는 scout/planner/implementer/reviewer/repairer다. Sandbox는 Role에 고정한다.
- Planner는 gpt-6.1-sol/high, 나머지는 gpt-6-luna/max를 기본으로 사용하고 매 실행에 model/reasoning을 명시한다.
- Built-in/global/project/run 순으로 설정을 병합하고 Role별 model/effort override를 지원한다. 기존 validation 설정은 호환된다.
- Task 생략 + stdin/stdout TTY이면 terminal menu를 열고, 기본 사용은 Task 입력 후 Enter로 실행한다. 번호 선택 customization과 custom model ID, project defaults 저장, 취소를 제공한다.
- 기존 Task argument direct mode와 stdout JSON을 유지한다. Non-TTY에서 Task 생략 시 usage error로 종료한다.
- TTY에서 Role/stage/model/reasoning/결과와 repair budget을 표시한다. Worker별 effective policy·elapsed·result·raw usage를 연결한다.
- 사용할 수 없는 model/effort에서는 fallback하지 않는다. 실제 로그인된 Codex end-to-end 실행과 회귀 테스트로 검증한다.
