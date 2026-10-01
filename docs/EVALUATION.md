# 평가 전략

## 1. 왜 Eval이 필요한가

Plan, Review, Skill, Repair, Subagent를 추가하면 시스템은 쉽게 더 복잡해집니다.

복잡해졌다는 사실이 좋아졌다는 의미는 아닙니다.

따라서 각 기능은 다음 중 하나를 실제로 개선하는지 확인해야 합니다.

- Task 성공률
- 첫 시도 성공률
- Human rework
- 품질 / 회귀 위험
- 개발자가 반복해서 해야 하는 지휘 작업

추가 Codex 사용량과 elapsed time은 비용으로 함께 기록합니다.

## 2. 기본 비교군

동일한 실제 Task를 가능한 한 같은 조건에서 비교합니다.

### A. Direct Codex

일반적인 방식으로 Codex에 Task를 직접 전달합니다.

### B. Codex + Skill

동일 Task에서 재사용 Skill 또는 표준 절차를 제공합니다.

### C. Codex DevFlow

동일 Task를 orchestration workflow로 실행합니다.

~~~text
Direct Codex
vs
Codex + Skill
vs
Codex DevFlow
~~~

DevFlow가 모든 지표에서 이겨야 하는 것은 아닙니다.

목표는 **어떤 종류의 Task에서 orchestration이 가치가 있는지** 찾는 것입니다.

## 3. Eval Dataset

실제 완료한 repository Task를 우선 사용합니다.

후보 유형:

- validation 추가
- API 동작 수정
- 예외 처리
- integration test
- transaction 변경
- query / index 변경
- retry
- idempotency
- async / event-driven 변경
- observability
- cross-module refactor

처음에는 10개 내외의 명확한 Task로 시작합니다.

각 Task에 저장할 정보:

~~~text
task id
repository commit
task prompt
acceptance criteria
필수 validation
risk / domain label
reference result
~~~

## 4. 통제 조건

가능한 한 동일하게 유지합니다.

- repository commit
- Codex model
- reasoning setting
- task prompt
- machine environment
- validation command
- timeout

Agent 실행은 비결정적일 수 있으므로 중요한 실험은 반복 실행을 고려합니다.

## 5. Outcome Metric

### Task success

최종 repository 상태가 acceptance criteria를 만족했는가.

### Validation pass

필수 build / test / lint가 통과했는가.

### First-pass success

Repair 전에 validation을 통과했는가.

### Human rework

Workflow 종료 후 사람이 수정해야 한 횟수 또는 시간.

### Unrelated change

요청 범위를 벗어난 파일 또는 동작 변경이 발생했는가.

## 6. Efficiency Metric

가능한 범위에서 수집합니다.

- total elapsed time
- Codex run count
- repair attempts
- validation attempts
- changed files
- Codex 도구가 노출하는 사용량 / credit 정보
- process / tool 실행 횟수

실제로 측정할 수 없는 token 또는 비용 수치를 임의 계산해서 주장하지 않습니다.

## 7. Process Metric

- policy가 Plan을 요구했을 때 Plan이 생성됐는가
- 단순 Task에 불필요한 Plan을 강제했는가
- 필요한 Review를 선택했는가
- 불필요한 Review를 호출했는가
- repair limit을 지켰는가
- Exec이 실제 diff와 validation 결과를 반영하는가

## 8. Router Eval

Routing 품질과 Coding 품질을 분리해서 봅니다.

사람이 일부 Task의 기대 workflow를 라벨링하고 DevFlow 결과와 비교합니다.

후보 지표:

- complexity agreement
- unnecessary complex routing
- dangerous under-routing
- reviewer selection precision
- reviewer selection recall

위험한 Task를 SIMPLE로 분류하는 오류는 단순 Task를 과도하게 계획하는 오류보다 더 큰 비용으로 취급할 수 있습니다.

## 9. Trade-off 해석

다음 결과도 유효합니다.

~~~text
Task success    증가
Human rework    감소
Elapsed time    증가
Codex usage     증가
~~~

복잡한 Task에서 human rework 감소가 충분히 크다면 추가 machine usage를 받아들일 수 있습니다.

반대로 단순 Task에서 품질 차이가 없고 시간만 증가한다면 SIMPLE path로 보내야 합니다.

## 10. 첫 Eval

Subagent를 추가하기 전에 먼저 다음을 비교합니다.

~~~text
Direct Codex

vs

Plan → Implement → Validate → Review
~~~

기본 workflow가 medium / complex Task에서 의미 있는 이점을 만들지 못한다면 Multi-Agent를 추가할 근거도 부족합니다.

## 11. 포트폴리오에서 허용되는 주장

좋은 주장:

> 동일 조건의 실제 N개 개발 Task에서 DevFlow 적용 전후 Task success, first-pass success, human rework, elapsed time을 비교했고 X와 Y의 trade-off를 확인했다.

약한 주장:

> Multi-Agent를 구축해서 생산성을 높였다.

숫자와 실험 조건이 없는 성능 주장은 하지 않습니다.


## 12. V0에서 실제로 수집하는 항목

001 구현은 `run.json`과 `exec.md`에 다음 값을 기록한다.

| 항목 | 근거와 해석 |
| --- | --- |
| validation pass | 설정된 모든 shell 명령의 exit code 0, timeout 없음 |
| first-pass validation | 첫 validation attempt 결과; 명령 미설정이면 null |
| elapsed | 전체 run과 subprocess별 monotonic elapsed seconds |
| Codex run count | 시작한 worker 수; 실패한 실행도 포함 |
| repair/validation attempts | 실행 이력의 길이 |
| changed files | 시작·종료 snapshot의 차이; 기존 변경은 baseline으로 보존 |
| usage | Codex JSONL의 usage 객체 원형; 미노출이면 null |
| workflow/plan/review | deterministic 선택 결과와 실제 worker artifact |

`validation pass`는 사용자의 acceptance criteria 충족을 자동으로 확정하지 않는다. Review 결과와 task success 역시 구분한다. Human rework, unrelated change, 품질 개선, credit·비용 개선은 현재 자동 측정하지 않는다.

검증 명령 미설정은 `unavailable`이며 최종 run은 `unverified`가 된다. Codex 응답의 성공 선언으로 이 상태를 바꾸지 않는다. Validation 또는 review가 실패하면 최대 repair 횟수만큼 반복하고, 실행 오류·schema 오류·중단은 evidence를 남기고 종료한다.

테스트는 fake executable을 통한 제어 로직 검증과 실제 로그인된 Codex를 통한 end-to-end 실행으로 구분한다. Fake usage는 parser 검증용 값이며 실제 사용량 집계와 비교 실험에 포함하지 않는다. 구체적인 실행 환경·명령·결과·제한은 [001 Exec](exec/001-initial-implementation.md)에 기록한다. V0에서는 Direct Codex 비교 실험과 eval harness를 구현하지 않았다.


## 13. 002에서 고정한 실행 조건

Core Role은 scout/planner/implementer/reviewer/repairer다. 실행 전에 effective model/reasoning/sandbox를 계산하며 worker별 started/finished, elapsed, exit/timeout/interruption 및 CLI raw usage를 연결한다. Default policy는 planner=gpt-6.1-sol/high, 나머지=gpt-6-luna/max다. Global/repository/run override를 적용한 최종 값은 settings와 workers에 남긴다.

metrics.roles는 실제 실행된 Role의 run count, elapsed와 raw usage를 모은다. Simple에서 생략한 planner/reviewer를 실행 수에 포함하지 않는다. Model별 품질 순위, 자동 model 승격, 생산성 개선의 결론은 내리지 않는다. 실행 재현성과 Role별 관측을 위한 변경이다.

실제 TTY, fake backend 회귀 테스트와 로그인된 Codex 검증 결과는 [002 Exec](exec/002-worker-role-model-interactive-ux.md)에 기록한다.
