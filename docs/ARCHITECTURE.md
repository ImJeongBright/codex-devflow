# 아키텍처

## 구현된 책임 경계

Codex는 저장소 탐색, 의미 분석, 계획, 구현, 실패 진단, 일반 리뷰를 담당한다. DevFlow는 schema 검증, routing, 순차 상태 전이, subprocess 실행, timeout, repair 한도, validation 판정, artifact와 metric 수집을 담당한다.

DevFlow는 Python 3.11+ 표준 라이브러리로 구현되며 POSIX 환경에서 실행한다.

| 컴포넌트 | 구현 | 책임 |
| --- | --- | --- |
| CLI/config | `codex_devflow/cli.py` | task·repository·검증 명령·timeout·repair 설정, 종료 코드 |
| Config policy | `codex_devflow/config.py` | global/project/run 병합과 project role 저장 |
| Role policy | `codex_devflow/roles.py` | 다섯 Core Role, model/reasoning, 고정 sandbox |
| Terminal adapter | `codex_devflow/terminal.py` | interactive 입력, customization, stderr progress |
| Backend abstraction | `codex_devflow/backend.py` | `CodexExecutionBackend` protocol, `CodexCliBackend`, normalized result |
| Process | `codex_devflow/process.py` | stdin 전달, stdout/stderr 파일, exit code·elapsed, timeout/중단 시 process group 정리 |
| Schema/policy | `codex_devflow/schema.py` | version 1 analysis/plan/change/review schema와 두 경로 routing |
| Workflow | `codex_devflow/workflow.py` | 순차 단계 실행, repository lock, repair, checkpoint·최종 Exec |
| Repository evidence | `codex_devflow/repository.py` | Git root, 시작 전 snapshot, 변경 파일, tracked/untracked diff |

## 실행 흐름

~~~text
Task → Analyze → Policy
                  ├─ simple  → Implement → Validate
                  └─ planned → Plan → Implement → Validate → General Review

Validation 또는 Review 실패
  → repair 한도 확인 → Repair → Validate → planned이면 General Review
  → 한도 소진 시 failed

시작된 run의 모든 종료 → run.json / exec.md
~~~

`scope=local`, `regression_risk=low`, 모든 위험 flag=false일 때만 simple로 간다. 위험 flag는 database, transaction, async, concurrency, retry/idempotency, migration, external integration이다. unknown은 planned로 간다. `suggested_reviews`는 분석 evidence에 저장하며 V0는 General Review 하나만 실행한다.

Schema는 required fields, 추가 필드 금지, 타입, enum을 검사한다. 잘못된 JSON·schema·프로세스 실패는 error로 종료한다. 이 실행 오류에는 repair를 자동 적용하지 않는다. Repair budget은 validation/review 실패에 사용한다.

## Codex CLI backend

각 단계는 독립 `codex exec` 프로세스다. 공통 prompt에 원 task, plan, 검증 명령, 작업 경계를 전달한다. 인증은 로컬 Codex 설정을 따른다. 모델과 reasoning은 역할별 effective policy를 CLI에 명시적으로 전달한다.

- `--output-schema`: 단계별 JSON 응답 계약
- `--output-last-message`: 최종 structured 응답 파일
- `--json`: raw event stream과 노출된 usage 수집
- `--ephemeral`: Codex session 영구 보관 생략; DevFlow evidence는 별도 저장
- `-a never`: 자동화 중 승인 대기 없이 권한 범위 내에서 실행
- scout/planner/reviewer: `--sandbox read-only`
- implementer/repairer: `--sandbox workspace-write`

Prompt는 push, PR 생성, merge, commit, branch 삭제, 파괴적 DB 작업, subagent와 중첩 workflow를 금지한다. DevFlow 자체에는 해당 실행 단계가 없다. Codex가 사용할 수 있는 외부 tool과 정책은 로컬 CLI 환경에 영향을 받으므로 prompt를 독립적인 보안 경계로 보장하지 않는다. Sandbox 우회 옵션은 사용하지 않는다.

로컬 검증 기준 CLI는 0.158.0이다. 옵션 근거: [공식 non-interactive 문서](https://developers.openai.com/codex/noninteractive), [CLI reference](https://developers.openai.com/codex/cli/reference), 로컬 `codex exec --help`.

## Validation과 종료 판정

`.codex-devflow.json`의 `validation_commands` 또는 반복 `--validate` 옵션으로 명령 목록을 받는다. CLI 옵션은 파일 값을 대체한다. 명령은 target Git root에서 `/bin/sh -c`로 순차 실행하며 모든 명령의 stdout/stderr, exit code, elapsed, timeout을 기록한다.

모든 명령이 exit 0이고 timeout이 없을 때 validation passed다. 명령이 없으면 unavailable다. Planned review는 `passed`와 findings를 받고 high/critical finding이 있으면 실패로 처리한다. 실패 리뷰에는 finding이 필요하다.

| 상태 | 조건 |
| --- | --- |
| succeeded | validation passed, 필요한 review passed |
| unverified | validation unavailable, 필요한 review passed |
| failed | validation/review 실패, repair 한도 소진 |
| error | Codex 실행·JSON·Git evidence 등 오류 |
| interrupted | SIGINT/SIGTERM 중단 |

기본 repair는 최대 1회이고 0으로 끌 수 있다. Timeout 기본값 600초는 각 Codex 프로세스와 각 validation 명령에 각각 적용한다. 전체 run에 대한 별도 시간 한도는 없다.

## Artifact와 변경 추적

Target의 `.codex-devflow/runs/<UTC timestamp>-<random id>/`에 저장한다. 한 repository의 동시 run은 파일 lock으로 차단한다.

- `task.json`, `analysis.json`, `plan.json`, `plan.md`
- `baseline.json`, `baseline.diff`, `changes.diff`
- `steps/<sequence>-<role>/`: prompt, schema, response, process stdout/stderr, normalized result
- `validation/<attempt>/<command>/`: stdout/stderr
- `validation.json`, `review.json`, `repair.json`, `run.json`, `exec.md`

설정·repository 사전 검증 오류는 run 생성 전에 종료할 수 있다. 단계별 파일은 실행된 만큼 생성한다. Simple plan은 생략 사유만 기록한다. `run.json`을 단계 전환마다 갱신하고 정상 종료·실패·catch 가능한 중단 시 최종화한다. JSON은 임시 파일을 replace하여 저장한다.

시작 전과 종료 시 Git이 인식하는 파일의 내용 hash·mode·symlink target을 비교해 changed files를 산출한다. `.codex-devflow/`는 제외한다. 기존 미커밋 변경을 되돌리지 않는다. Review에 현재 diff와 시작 diff를 함께 제공한다. 현재 diff에는 기존 변경도 포함되므로 변경 파일 목록과 baseline을 같이 해석한다.

## 기록하는 metric과 제한

전체 elapsed, 단계별 elapsed·exit code, Codex 실행 횟수, validation/repair 횟수, 첫 validation 통과 여부, 변경 파일, CLI JSONL이 노출한 usage를 기록한다. Usage가 없으면 null이며 비용·credit을 추정하지 않는다. Plan 대비 변경점과 구현 제한은 worker 보고임을 Exec에 표시한다.

V0는 resume, SIGKILL/전원 종료 후 최종화, 다른 편집 도구와의 동시 변경 격리, ignored 파일 및 submodule 내부 변경의 완전한 추적을 지원하지 않는다. 대규모 diff는 별도 압축 없이 prompt에 포함하므로 context 한도가 적용된다. 신뢰하는 로컬 저장소와 validation 명령을 전제로 한다.

## 후속 단계

전문 review routing, reusable skills, 병렬 CLI worker, native subagent, API backend, eval harness는 [Roadmap](ROADMAP.md)의 후속 범위다. V0의 실제 관측 결과를 근거로 별도 계획을 작성한다.


## 002 Core Role과 모델 정책

`roles.py`의 Role enum은 scout, planner, implementer, reviewer, repairer 다섯 identity를 정의한다. Permission은 Role에서 파생되며 설정에서 바꿀 수 없다. Read-only는 scout/planner/reviewer, workspace-write는 implementer/repairer다.

`WorkerPolicy`는 role, model, reasoning_effort와 파생 sandbox를 표현한다. 기본값은 planner=gpt-6.1-sol/high, 나머지=gpt-6-luna/max다. 모델 품질에 관한 결론이 아니라 초기 실행 baseline이다.

`config.py`는 built-in → global → repository → CLI/run override 순으로 field별 병합한다. Global path는 `${XDG_CONFIG_HOME:-~/.config}/codex-devflow/config.json`, repository path는 기존 `.codex-devflow.json`이다. 기존 validation/timeout/repair 설정은 그대로 읽는다. 잘못된 role, permission 변경, 잘못된 model ID 형식이나 effort는 실행 전에 거부한다. Custom model ID는 허용하며 서버에서 사용할 수 없으면 error로 종료한다. 자동 fallback은 없다.

Backend는 `WorkerPolicy`를 받고 `--model MODEL`, `--config 'model_reasoning_effort="EFFORT"'`, 해당 Role의 sandbox를 직접 조합한다. Role별 별도 command builder는 없다.

## 002 Interactive input과 progress

`terminal.py`는 input/output adapter다. Task argument가 없고 stdin/stdout이 모두 TTY이면 terminal 입력을 연다. Task argument가 있으면 direct mode를 유지한다. Non-TTY에서 task가 없으면 usage error로 즉시 종료한다.

Input은 repository 확인, 한 줄 Task 또는 `:multi` 입력, effective defaults 확인, 번호 선택 customization, custom model ID, Run/Save project defaults/Cancel을 제공한다. 기본 흐름은 Task 입력 후 Enter로 실행한다. Save는 roles만 project config에 저장하고 기존 validation 설정을 보존한다.

Workflow는 선택적으로 event callback을 받는다. Worker 시작/완료, validation 명령과 결과, repair budget, finalize와 최종 요약을 보낸다. TTY progress adapter는 stderr에 쓴다. 기존 stdout 최종 JSON은 direct automation에서 유지된다. UI output이 BrokenPipe 등 OSError로 실패하면 progress만 중지한다.

표준 라이브러리 기반 line/menu UI이며 전체 화면 redraw나 arrow selector는 사용하지 않는다. 별도 TUI dependency는 없다.

## 002 Worker evidence

Run의 기존 schema_version=1과 steps를 유지하고 artifact_version=2를 추가한다. workers와 steps는 같은 실행 목록이다. Worker마다 sequence, Core Role, model, reasoning_effort, sandbox, status, started_at/finished_at, elapsed_seconds, exit_code, timeout, raw usage, process, error를 저장한다. Task/settings에는 모든 Role의 effective policy를 먼저 저장한다. Simple workflow는 scout/implementer를 실행하고 validation 실패 시 repairer를 추가한다. Planner/reviewer는 실행하지 않는다.

Codex worker가 중단되면 이미 노출된 usage와 ProcessResult도 보존한다. metrics.roles는 실제로 실행한 Role만 count, elapsed 및 raw usage와 연결한다. 기존 001 파일은 수정하거나 변환하지 않는다. 초기 output JSON 계약은 그대로 유지된다.
