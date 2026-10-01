# 002 — Worker Role, Model Policy, Interactive UX 실행 기록

## 결과

[002 계획](../plans/002-worker-role-model-interactive-ux.md)에 따라 Core Role, explicit model policy, 설정 병합, interactive 입력과 progress, worker evidence를 구현했다. 자동 테스트 50개와 설치된 CLI 검증을 통과했다. 로그인된 Codex CLI로 기본 interactive 실행, reviewer customization, direct 실행, 잘못된 모델의 실패 처리를 검증했다. 검증일은 2026-10-01(KST)이다.

## 실제 변경

- `roles.py`: scout/planner/implementer/reviewer/repairer 공통 identity, immutable WorkerPolicy, Role에 고정된 sandbox. Planner는 `gpt-6.1-sol/high`, 나머지는 `gpt-6-luna/max`를 기본으로 사용한다.
- `config.py`: built-in → global → repository → run 순으로 Role의 각 필드를 병합한다. 기존 validation/timeout/repair 설정, 반복 가능한 CLI override, project Role 기본값 저장을 지원한다. 잘못된 Role·설정·effort는 worker 시작 전에 거부한다.
- `backend.py`: 매 worker에 `--model`, `--config model_reasoning_effort`, Role의 sandbox를 명시한다. 모델 대체나 재시도 fallback을 추가하지 않았다. 중단 전에 노출된 usage도 보존한다.
- `terminal.py`, `cli.py`: Task 생략 + stdin/stdout TTY에서 입력 메뉴를 연다. Task 후 Enter로 실행하거나 Role별 preset/custom model과 effort를 선택한다. `:multi`로 여러 줄 입력, project 기본값 저장, 취소를 제공한다. Non-TTY Task 생략은 exit 2, 실행 전 취소는 exit 130이며 worker를 시작하지 않는다.
- `workflow.py`: terminal과 분리된 progress event를 전달한다. TTY adapter는 Role/model/reasoning, validation 명령·실패 출력, repair budget, finalize와 완료 요약을 stderr에 표시한다. Stdout 최종 JSON 계약을 유지한다.
- Artifact: 기존 `schema_version: 1`, `steps`와 structured output을 유지하고 `artifact_version: 2`, `workers`, effective settings, Role별 metrics를 추가했다. Worker의 sequence, policy, status, timestamp, elapsed, exit/timeout/error, raw usage와 process를 함께 저장한다. 성공·실패·중단에서 단계별 `result.json`과 `run.json`이 일치한다. 실행하지 않은 Role은 workers/metrics에 생성하지 않는다.
- README, PRD, Architecture, Evaluation, Manual을 실제 동작에 맞췄다. README의 부정 후 대조 표현을 정리했다. 로컬 artifact·cache·빌드 결과·`.DS_Store`를 ignore한다.

## 계획 대비 변경점

표준 라이브러리의 번호 선택 메뉴를 사용했다. 계획의 화면 예시는 책임과 입력 흐름으로 구현했으며 fullscreen widget이나 방향키 selector는 추가하지 않았다. Task를 충분히 길게 입력하거나 `:multi`로 여러 줄을 입력할 수 있다. Terminal adapter와 workflow engine 경계를 유지하면서 runtime dependency를 추가하지 않았다.

Global 설정 경로는 `${XDG_CONFIG_HOME:-~/.config}/codex-devflow/config.json`으로 확정했다. UI의 Save는 repository `.codex-devflow.json`의 Role 기본값만 저장하고 validation 등 기존 설정을 보존한다. Run only는 파일을 변경하지 않는다. 모델 preset은 계획의 두 모델이며 custom ID 경로를 제공한다. 모델/effort 조합의 실제 지원 여부는 Codex 서버가 판정한다.

CLI 이름은 `--role-model ROLE=MODEL`, `--role-reasoning ROLE=EFFORT`로 확정했다. Output schema version은 변경하지 않고 artifact version으로 새 evidence를 구분했다. 기존 001 artifact를 변환하지 않았다.

작업 시작 시 001의 소스·테스트·설치 파일과 Manual/PRD/Exec가 working tree에 있었으나 Git에는 아직 추적되지 않았다. 002 실행에 필요한 V0 기반도 함께 커밋 대상에 포함했다. 기존 미추적 runtime 오류 전달 계획은 번호 중복을 피하려고 `003-runtime-error-reporting.md`로 옮기고 001 Exec의 링크를 갱신했다. 해당 기능은 구현하지 않았다.

## 자동 테스트와 설치 검증

환경은 macOS, Python 3.12.1, Codex CLI 0.158.0, ChatGPT 로그인이다.

| 검증 | 실제 결과 |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 50개 통과, unittest 보고 시간 21.714초, exit 0 |
| 기존 001 회귀 | 27개 유지: routing/schema, validation, bounded repair, timeout, signal/process 종료, run lock, artifact |
| 002 신규 | 23개: Role/기본값/권한, 설정 우선순위, argv와 artifact, 실패/timeout/중단 usage, no fallback, 입력/custom/save/cancel, 실제 PTY, progress와 stdout/stderr 실패 출력 |
| Wheel 빌드·임시 venv 설치 | `pip install --no-index --no-build-isolation --no-deps --no-cache-dir .` exit 0 |
| 설치된 console CLI | `/tmp`에서 임시 Git target과 fake executable로 실행; reviewer override와 succeeded/exit 0 확인 |

자동 테스트의 fake executable은 subprocess와 실제 signal/PTY를 사용한다. Invalid model, 서버가 effort를 거부하는 경우, repairer의 정책 전달은 fake 응답으로 재현한다. 설치 검증은 기존 build dependency를 사용할 수 있는 임시 venv에서 수행했다.

## 실제 Codex 검증

임시 Git 저장소의 작은 SQLite invoice fixture에서 순차 실행했다. Fixture의 `AGENTS.md`는 `ledger.py`, `receipt.py`, `test_invoice.py`만 수정하도록 제한한다. `acceptance.py`, 설정과 지시 파일은 최초 Git HEAD와 동일한지 hash/내용으로 확인했다. Validation은 `python3 -m unittest -v`, `python3 acceptance.py` 두 명령이다.

| 시나리오 | Run ID | 결과 |
| --- | --- | --- |
| A: Task 후 Enter, 기본 interactive | `20261001T022547Z-f5d7ef9ee4` | planned succeeded, 222.103초, 4 workers, 변경 3개, 6 tests 및 acceptance 통과, review passed, repair 0 |
| B: reviewer만 interactive override | `20261001T023304Z-584670f8c5` | planned succeeded, 151.373초, 4 workers, 변경 2개, 7 tests 및 acceptance 통과, review passed, repair 0 |
| C: Task argument direct | `20261001T024157Z-15b805fa7f` | simple succeeded, 95.141초, stdout JSON 한 줄, scout/implementer만 실행, docstring 변경 1개, 7 tests 및 acceptance 통과 |
| D: scout에 invalid-model 지정 | `20261001T023310Z-20f5ebc3b7` | error/scout, CLI exit 2, worker exit 1, worker 1개, 자동 모델 대체 없음 |

A는 total-only DB의 데이터 보존 migration, unit_price/quantity 저장, 성공 insert commit, bool 제외 정수 제약과 invalid input의 insert 방지를 구현했다. Worker가 수정할 수 없는 acceptance도 통과했다.

B는 `idx_invoices_total`을 `IF NOT EXISTS`로 생성하고 인덱스 존재/재초기화 안전성 테스트를 추가했다. Reviewer만 `gpt-6.1-sol/high`이고 scout/implementer는 `gpt-6-luna/max`, planner는 기존 `gpt-6.1-sol/high`다. Run only를 선택해 repository 기본값이 저장되지 않았음을 확인했다.

C의 첫 task는 README 작성이었으나 fixture의 수정 허용 범위 밖이라 구현 worker가 변경하지 않았다. Run `20261001T023634Z-94ec5c7df7`은 validation 통과로 succeeded, 85.490초, changed files 0이었다. Worker의 계획 대비 변경점/제한에 요청 문서 미작성 사유가 남았다. 따라서 이 첫 실행을 Task 완료 증거로 사용하지 않는다. 허용된 `test_invoice.py`의 module docstring으로 task를 다시 지정하고 direct 실행과 실제 변경을 확인했다. 최종 C는 원 테스트 함수와 구현을 보존하며 요청한 설명을 추가했다. Implementer 자체는 검증을 실행하지 않았다고 보고했으며 이후 DevFlow validation 단계에서 두 명령을 실행해 통과했다. 이 관측은 validation 통과 상태와 사용자 요구 충족을 별도로 확인해야 한다는 V0 제한도 보여준다.

D는 실제 서버의 HTTP 400 `invalid_request_error`와 `The 'invalid-model' model is not supported when using Codex with a ChatGPT account.` 메시지를 raw stdout에 보존했다. Codex 자체의 fallback metadata 경고도 있었지만 DevFlow는 다른 모델로 실행하지 않았고 다음 worker를 시작하지 않았다.

각 worker의 process argv에서 model/effort/sandbox가 metadata와 일치하는지, `result.json`과 workers가 같은지, 기존 steps와 workers가 같은지 직접 검사했다. 모든 정상 worker에 실제 CLI usage와 시작/종료 시각이 있었다. A/B/C에서 repairer는 실행하지 않았으므로 worker 기록을 만들지 않았다.

### 보존한 증거

- [검증 JSON](002-verification.json): 실제 task/정책/argv/lifecycle/raw usage/validation 출력/review, immutable fixture 검사, source와 원 artifact SHA-256. 임시 경로는 placeholder로 치환했다.
- [50개 테스트 출력](002-tests.txt).
- [기본 interactive transcript](002-terminal-default.txt), [reviewer customization transcript](002-terminal-custom.txt).
- 전체 로컬 raw evidence는 임시 fixture의 `.codex-devflow/runs/<run-id>/`에 있다. 요약 JSON과 transcript는 이 저장소의 `.codex-devflow/verification/002/`에도 남아 있다. 임시 파일의 장기 보존을 보장하지 않으므로 위의 휴대 가능한 증거를 커밋한다.

## 완료 조건 확인

| DoD | 확인 근거 |
| --- | --- |
| 1. Core Role identity | Role enum, worker/result/metrics, 전체 policy integration test |
| 2–3. Explicit/default policy | 고정 defaults 테스트, 실제 A의 planner와 나머지 argv/evidence |
| 4. Role override | field별 config 우선순위, CLI tests, 실제 B reviewer만 변경 |
| 5–6. 기본 interactive | 실제 PTY의 Task 입력 후 Enter; model 입력 없이 A 완료 |
| 7. Direct 유지 | Task argument 자동 테스트 및 실제 C, stdout JSON 한 줄 |
| 8. Non-TTY 안전 | Task 생략 시 prompt 없이 usage error/exit 2 테스트 |
| 9. Worker evidence | 성공/error/timeout/interruption 테스트, 실제 argv/result 일치와 usage 확인 |
| 10. No fallback | invalid config 사전 거부, fake model/effort 거부, 실제 D 서버 오류 |
| 11. 회귀 및 신규 테스트 | 27개 기존 + 23개 신규 = 50개 통과 |
| 12. 실제 E2E | 로그인된 CLI의 A/B planned 구현·validation·review 완료 |
| 13. 실행 기록 | 본 문서와 검증 JSON/테스트/terminal transcript |

## 발견한 제한

- 상위 Codex sandbox 안에서 중첩 CLI를 실행하면 app-server 초기화가 Operation not permitted로 실패했다. 실제 검증은 호스트 실행 권한에서 수행했고 각 worker의 sandbox 설정은 유지했다.
- 실제 A/B/C에서는 repair가 필요하지 않았다. 실제 모델의 repair 성공으로 해석하지 않는다. Repair의 정책과 bounded retry는 fake 통합 테스트로 확인했다.
- 이 실행은 작은 SQLite fixture의 기능 확인이다. 모델 간 품질·생산성·비용 우열을 측정하지 않았다. Model 기록은 CLI에 요청한 ID이며 서버 alias를 독립적으로 검증하지 않는다.
- Usage는 CLI가 노출한 원형 이벤트를 연결한다. 없는 usage를 추정하거나 비용으로 환산하지 않는다.
- Global 설정은 파일 편집으로 관리하고 UI에서는 project 기본값만 저장한다. 지원되지 않는 모델/effort의 구체적인 서버 원인은 raw log에서 확인한다. 요약 원인 전달 개선은 003의 후속 범위다.
- macOS에서 검증했다. Linux 실행, fullscreen/방향키 UX, 모델 catalog 자동 탐색은 이번에 검증하거나 구현하지 않았다.
- Workflow succeeded는 설정된 validation 및 필요한 review 통과를 의미한다. Simple 경로에서는 별도 reviewer가 없으며 C 첫 실행처럼 요청 미수행이 implementation limitations에 기록될 수 있다. Diff와 Exec의 수용 검토가 필요하다.

## 후속 작업

[003 runtime 오류 전달 계획](../plans/003-runtime-error-reporting.md)을 별도로 검토한다. 실제 프로젝트 사용에서 Role별 elapsed/usage, validation과 repair 진입 evidence를 축적한다. 이후 기능은 새로운 계획과 관측 결과를 근거로 정한다.
