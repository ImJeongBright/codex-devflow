# Codex DevFlow 사용자 매뉴얼

Codex DevFlow에 개발 요청 하나를 전달해 로컬 Git 저장소를 분석하고, 구현·검증·리뷰 결과를 기록하는 방법을 설명합니다.

## 1. 준비

macOS 또는 Linux, Python 3.11 이상, Git, 로그인된 Codex CLI가 필요합니다. DevFlow를 실행할 때 Codex CLI를 찾을 수 있는지와 로그인이 됐는지 확인합니다.

~~~bash
codex --version
codex login status
~~~

저장소를 내려받은 뒤 가상 환경에 설치합니다.

~~~bash
cd /path/to/codex-devflow
python3 -m venv .venv
.venv/bin/python -m pip install -e .
~~~

다른 환경에 설치하지 않고 바로 사용하려면 DevFlow 저장소의 최상위 디렉터리에서 `python3 -m codex_devflow` 명령을 실행할 수 있습니다.

## 2. 개발 요청 실행

터미널에서 다음 명령을 입력하면 대화형 입력 화면이 열립니다.

~~~bash
.venv/bin/codex-devflow feature
~~~

현재 Git repository를 확인한 뒤 Task를 입력하고 Enter로 실행합니다. 추가 model 설정을 입력할 필요가 없습니다. 여러 줄 Task는 `:multi`를 입력하고 내용을 쓴 뒤 한 줄에 `.`만 입력해 마칩니다.

- 기본 화면의 Enter 또는 `r`: 이번 선택으로 실행합니다.
- `c`: Role 번호를 고르고 model과 reasoning을 변경합니다. Model 메뉴의 `c`는 custom model ID 입력입니다. 각 메뉴에서 Enter를 누르면 현재 값을 유지합니다.
- `s`: 현재 role policy를 project 기본값으로 저장합니다. 저장 후 Enter로 실행하거나 `q`로 실행을 취소할 수 있습니다. 기존 validation/timeout/repair 값은 보존됩니다.
- `q`, Ctrl+C 또는 입력 종료: Codex worker를 시작하기 전에 취소합니다.

기본값은 global/project 설정이 반영된 effective defaults입니다. Task를 CLI argument로 전달하면 대화형 화면을 열지 않고 바로 실행합니다. Stdin/stdout이 TTY가 아닌 script나 CI에서는 Task 생략 시 종료 코드 2로 즉시 종료합니다.

요청, 대상 저장소, 검증 명령을 한 번에 전달합니다.

~~~bash
.venv/bin/codex-devflow feature \
  "요청을 구체적으로 작성한다. 성공 조건과 영향을 받는 동작을 포함한다." \
  --repo "/path/to/target-repository" \
  --validate "python3 -m unittest discover -s tests -v"
~~~

공백이 포함된 경로와 task는 따옴표로 감쌉니다. `--repo`를 생략하면 현재 디렉터리가 Git 저장소인지 확인하고 해당 저장소를 대상으로 삼습니다. 입력 task는 비워 둘 수 없습니다.

요청에는 바뀌어야 할 동작, 성공으로 볼 조건, 관련 제약을 적습니다. 예를 들어 다음처럼 작성할 수 있습니다.

~~~text
사용자가 잘못된 이메일 주소로 가입하면 400 응답을 반환하도록 수정한다.
기존의 정상 가입 동작은 유지하고, 이메일 검증 테스트를 추가한다.
~~~

Task에 적힌 검증 조건과 실제 테스트 명령을 함께 전달하면 결과를 확인하기 쉽습니다. DevFlow는 마지막에 diff와 리뷰를 사람이 확인하도록 실행 기록을 남깁니다.

## 3. Validation 설정

대상 Git 저장소의 루트에 `.codex-devflow.json` 파일을 두면 반복 실행에 사용할 명령, 각 프로세스 제한 시간, repair 한도를 저장할 수 있습니다.

~~~json
{
  "validation_commands": [
    "python3 -m unittest discover -s tests -v",
    "python3 -m compileall -q src"
  ],
  "timeout_seconds": 600,
  "max_repairs": 1
}
~~~

설정 값은 다음과 같습니다.

- `validation_commands`: 저장소 루트에서 실행할 shell 명령의 목록입니다. 빈 목록은 허용되며, 이 경우 결과는 `unverified`입니다.
- `timeout_seconds`: 각각의 Codex worker와 각각의 validation 명령에 적용할 제한 시간입니다. 전체 run 시간 제한은 별도로 적용하지 않습니다.
- `max_repairs`: validation 또는 review 실패 뒤 허용할 자동 수정 횟수입니다. 기본값은 1, 끄려면 0으로 설정합니다.

CLI 옵션으로 실행할 때 설정값을 바꿀 수 있습니다.

~~~bash
.venv/bin/codex-devflow feature "요청" \
  --repo "/path/to/target-repository" \
  --validate "npm test" \
  --validate "npm run lint" \
  --timeout 900 \
  --max-repairs 0
~~~

`--validate`를 한 번 이상 지정하면 설정 파일의 명령 목록 전체를 CLI 명령으로 바꿉니다. timeout과 repair도 각각 옵션을 지정한 값이 설정 파일을 덮어씁니다. `--codex /path/to/codex`는 Codex CLI 실행 파일 경로를 지정합니다.

Validation 명령은 대상 저장소 루트에서 `/bin/sh -c`로 실행됩니다. 프로젝트에서 신뢰하는 명령을 지정하세요.

### Role별 model과 reasoning

별도 설정이 없을 때의 정책은 다음과 같습니다.

| Role | Model | Reasoning | Sandbox |
| --- | --- | --- | --- |
| scout | gpt-6-luna | max | read-only |
| planner | gpt-6.1-sol | high | read-only |
| implementer | gpt-6-luna | max | workspace-write |
| reviewer | gpt-6-luna | max | read-only |
| repairer | gpt-6-luna | max | workspace-write |

Global 설정은 `~/.config/codex-devflow/config.json`에서 읽습니다. `XDG_CONFIG_HOME`이 있으면 그 경로 아래 `codex-devflow/config.json`을 사용합니다. Global 파일은 필요할 때 직접 만들 수 있습니다. Project 설정은 기존 `.codex-devflow.json`의 `roles`를 확장합니다.

~~~json
{
  "validation_commands": ["npm test"],
  "roles": {
    "reviewer": {"model": "gpt-6.1-sol", "reasoning_effort": "high"}
  }
}
~~~

설정은 built-in → global → project → CLI/interactive 선택 순서로 병합합니다. 각 Role의 model과 reasoning을 독립적으로 덮어씁니다. Sandbox는 Role에 고정되어 설정으로 변경할 수 없습니다.

~~~bash
codex-devflow feature "개발 요청" --repo /path/to/project \
  --role-model reviewer=gpt-6.1-sol \
  --role-reasoning reviewer=high
~~~

다른 Role도 같은 옵션을 반복해서 지정합니다. Custom model ID를 허용하지만 model/effort의 실제 사용 가능 여부는 설치된 Codex와 계정에서 결정됩니다. 지원되지 않으면 실패로 종료하고, 다른 model로 자동 fallback하지 않습니다. 모델 품질이나 비용 차이에 대한 결론을 전제하지 않습니다.

## 4. 실행되는 단계

모든 task에서 읽기 전용 Scout가 먼저 저장소를 분석합니다. 분석 결과가 `local`, `low` risk이고 DB, transaction, async, concurrency, retry/idempotency, migration, external integration 위험 신호가 모두 false일 때 simple 경로를 선택합니다.

~~~text
simple:  Analyze → Implement → Validate
planned: Analyze → Plan → Implement → Validate → General Review
~~~

분석 결과가 불확실하거나 위험 신호가 있으면 planned 경로로 갑니다. Validation 또는 Review가 실패하면 설정된 횟수만큼 repair한 뒤 다시 검증합니다. 실패가 한도 안에서 해결되지 않으면 run은 `failed`로 끝납니다.

Scout, Plan, Review는 Codex CLI의 `read-only` sandbox로 실행합니다. Implement와 Repair는 `workspace-write` sandbox를 사용합니다. DevFlow의 workflow에는 push, PR 생성, merge, branch 삭제 작업이 없습니다.

## 5. 실행 결과 읽기

명령이 끝나면 stdout에 run 상태와 artifact 경로가 JSON 한 줄로 출력됩니다.

~~~json
{"status":"succeeded","workflow":"planned","run_dir":"/path/to/target/.codex-devflow/runs/<run-id>","error":null}
~~~

`run_dir`에서 다음 파일을 확인합니다.

| 파일 | 내용 |
| --- | --- |
| `task.json` | 전달한 task와 실행 설정 |
| `analysis.json` | Scout의 검증된 구조화 분석 |
| `plan.json`, `plan.md` | planned workflow의 구조화 계획과 읽기용 문서. Simple에서는 `plan.md`에 생략 이유 기록 |
| `baseline.diff` | run 시작 전 이미 존재한 Git diff |
| `changes.diff` | 종료 시점의 Git diff. 시작 전 변경도 포함 |
| `validation.json` | 명령별 결과, 종료 코드, 경과 시간, timeout, stdout/stderr 경로 |
| `review.json` | 실제 실행된 General Review 결과 |
| `repair.json` | repair 시도와 해당 시점의 실패 증거 |
| `run.json` | 상태 전이, 단계, 변경 파일, 제한, 지표를 담은 최종 기록 |
| `run.json`의 `workers` | 실제 실행된 Role의 model/reasoning/sandbox, 상태, elapsed, 종료 코드, timeout, usage |
| `exec.md` | 실행 결과를 사람이 읽을 수 있도록 정리한 문서 |
| `steps/<순번>-<역할>/` | 각 Codex 단계의 prompt, JSON Schema, 응답, stdout/stderr와 실행 결과 |
| `validation/<시도>/<명령>/` | validation 명령별 stdout과 stderr |

시작 전에 있던 수정은 되돌리지 않습니다. `changed_files`는 시작 전후의 파일 내용과 권한 차이를 기록하며, `changes.diff`에는 기존 수정도 나타날 수 있습니다. 새 artifact 디렉터리는 `.codex-devflow/` 안에 만들어집니다. 대상 저장소의 `.gitignore`에 `.codex-devflow/`를 추가하는 것을 권장합니다.

## 6. 상태와 종료 코드

| 상태 | 종료 코드 | 의미 |
| --- | ---: | --- |
| `succeeded` | 0 | 설정한 모든 Validation과 필요한 Review를 통과 |
| `failed` | 1 | Validation 또는 Review 실패가 repair 한도 안에서 해결되지 않음 |
| `error` | 2 | 설정, 저장소, Codex 실행, structured output 또는 실행 증거 오류 |
| `unverified` | 3 | Validation 명령이 설정되지 않아 검증되지 않음 |
| `interrupted` | 130 | SIGINT 또는 SIGTERM으로 실행을 중단 |

`unverified`는 검증 성공을 뜻하지 않습니다. `succeeded`도 요청의 최종 수용을 자동으로 승인하지 않습니다. 종료 후 `exec.md`, `validation.json`, diff와 리뷰 결과를 확인하세요.

실행 중 Ctrl+C를 누르면 현재 subprocess group을 정리하고 중단 상태를 artifact에 기록합니다. 한 Git 저장소에서는 동시에 한 DevFlow run만 시작할 수 있습니다.

TTY에서는 현재 Role의 model/reasoning과 시작·완료 상태, validation 명령/출력, repair 횟수, 최종 요약과 Exec 경로를 stderr에 표시합니다. Direct mode에서 stdout을 파일로 redirect하면 기존 최종 JSON만 저장되며 interactive prompt가 생기지 않습니다.

## 7. 문제가 생겼을 때

- **`codex`를 찾을 수 없음:** Codex CLI 설치 상태를 확인하거나 `--codex`에 실행 파일 경로를 전달합니다.
- **로그인 오류:** `codex login status`로 상태를 보고 필요하면 `codex login`을 실행합니다.
- **Validation이 실패함:** `validation.json`에서 실패한 명령과 stdout/stderr 파일을 확인합니다. Repair 횟수를 모두 사용하면 run이 `failed`로 끝납니다.
- **결과가 `unverified`:** `.codex-devflow.json`이나 `--validate`에 실제 검사 명령을 지정하고 다시 실행합니다.
- **Codex 단계가 실패함:** 해당 `steps/<순번>-<역할>/stderr.log`와 `stdout.log`, `run.json`의 `error`를 확인합니다. 사용량 한도, network 또는 sandbox 초기화 문제는 Codex CLI 메시지에 남을 수 있습니다.
- **run이 이미 실행 중이라는 오류:** 해당 저장소의 다른 run이 끝났는지 확인한 후 다시 실행합니다.

## 8. 사용 시 유의할 점

Validation 명령은 저장소 루트에서 현재 사용자 권한으로 실행됩니다. 설정한 명령을 이해하고 신뢰할 수 있는지 확인하세요. Task, prompt, 프로그램 출력과 diff가 실행 기록에 포함될 수 있으므로 artifact를 공유하기 전에 내용을 확인합니다.

Usage 값은 Codex CLI 이벤트가 제공할 때만 기록됩니다. DevFlow는 사용량이나 비용을 추정하지 않습니다. 종료된 run의 이어 하기는 지원하지 않습니다.

개발자 중심의 PRD, 아키텍처, 완료 조건과 검증 내역은 저장소 [README 문서 목록](../README.md)을 참고하세요.
