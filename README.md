# codex-devflow

하나의 개발 요청을 **분석 → 계획 → 구현 → 검증 → 리뷰 → 실행 기록**으로 연결하는 로컬 개발 도구입니다. 로그인된 Codex CLI를 실행 엔진으로 사용하고, workflow 상태·timeout·repair 한도·검증 결과·artifact 저장은 Python 코드로 관리합니다.

## 실행 흐름

~~~text
Task → Read-only Scout → Deterministic Policy
                         ├─ simple:  Implement → Validate
                         └─ planned: Plan → Implement → Validate → General Review

Validation / Review 실패 → Repair → 다시 Validate / Review (설정한 한도까지)
시작된 run의 모든 종료 → run.json + exec.md + 단계별 evidence
~~~

분석 결과가 local/low risk이고 DB, transaction, async, concurrency, retry/idempotency, migration, external integration 신호가 모두 false이면 simple 경로를 선택합니다. 나머지는 planned 경로를 선택합니다.

각 Codex 단계는 독립적인 `codex exec` 프로세스로 순차 실행합니다. Scout·Plan·Review는 `read-only`, Implement·Repair는 `workspace-write` sandbox를 사용합니다.

## 시작하기

가상 환경에 설치한 뒤, 터미널에서 다음 명령만 입력하면 Task를 입력할 수 있습니다.

~~~bash
.venv/bin/codex-devflow feature
~~~

Task 입력 후 Enter를 누르면 설정된 기본 policy로 실행합니다. `c`로 Role별 model/reasoning을 조정하고 `s`로 project 기본값을 저장할 수 있습니다. 설치 및 상세 사용법은 [사용자 매뉴얼](docs/MANUAL.md)을 참고하세요.

필요 환경: Python 3.11+, POSIX(macOS/Linux), Git, 로그인된 Codex CLI.

~~~bash
codex login
python3 -m codex_devflow feature "개발 요청" --repo /path/to/repository \
  --validate "python3 -m unittest discover -s tests -v"
~~~

위 명령은 이 프로젝트 디렉터리에서 실행합니다. CLI를 설치하면 다른 디렉터리에서도 사용할 수 있습니다.

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/codex-devflow feature "개발 요청" --repo /path/to/repository
~~~

Codex 인증은 설치된 CLI 설정을 따릅니다. 모델과 reasoning은 아래의 역할별 정책을 명시적으로 전달합니다. DevFlow에는 API client나 API key 관리 기능이 없습니다. 실제 Codex 실행에는 계정의 사용량과 네트워크 연결이 필요합니다.

## 프로젝트별 검증 설정

Target Git 저장소 루트에 `.codex-devflow.json`을 작성합니다.

~~~json
{
  "validation_commands": ["python3 -m unittest discover -s tests -v"],
  "timeout_seconds": 600,
  "max_repairs": 1
}
~~~

- `--validate`를 반복해서 여러 명령을 전달할 수 있습니다. 전달하면 설정 파일의 명령 목록을 대체합니다.
- `--timeout`은 각 Codex 프로세스와 각 validation 명령의 제한 시간(초)입니다.
- `--max-repairs 0`은 자동 수정을 끕니다. 기본값은 1입니다.
- `--codex /path/to/codex`로 실행 파일을 지정할 수 있습니다.
- 설정한 validation 명령은 Git 저장소 루트에서 `/bin/sh -c`로 실행합니다. 사용자가 신뢰하는 명령을 설정해야 합니다.
- 검증 명령이 없으면 `unavailable`로 기록하고 최종 결과는 `unverified`로 남깁니다.

| 종료 상태 | CLI 코드 | 의미 |
| --- | --- | --- |
| `succeeded` | 0 | 설정된 validation과 필요한 review 통과 |
| `failed` | 1 | repair 한도 내 해결하지 못한 validation/review 실패 |
| `error` | 2 | 실행·schema·설정 오류 |
| `unverified` | 3 | validation 미설정, 필요한 review는 통과 |
| `interrupted` | 130 | SIGINT/SIGTERM으로 중단 |

설정·repository 오류는 run 생성 전에 종료될 수 있습니다. 작업의 최종 수용 여부는 사용자가 결과와 diff를 확인해 판단합니다.

## Worker 모델 정책

| Role | Model | Reasoning | Sandbox |
| --- | --- | --- | --- |
| scout | gpt-6-luna | max | read-only |
| planner | gpt-6.1-sol | high | read-only |
| implementer | gpt-6-luna | max | workspace-write |
| reviewer | gpt-6-luna | max | read-only |
| repairer | gpt-6-luna | max | workspace-write |

설정 우선순위는 built-in → global → repository → 이번 실행 선택/CLI override입니다. Global 설정은 `${XDG_CONFIG_HOME:-~/.config}/codex-devflow/config.json`의 JSON을 읽습니다. Repository 설정의 `roles`에서 Role별 `model`, `reasoning_effort`를 부분 지정할 수 있습니다.

~~~bash
codex-devflow feature "개발 요청" --repo /path/to/project \
  --role-model reviewer=gpt-6.1-sol --role-reasoning reviewer=high
~~~

`c` → Role 선택 → Model 메뉴에서 Codex의 로컬 모델 목록을 확인할 수 있습니다. 목록은 `$CODEX_HOME/models_cache.json` 또는 `~/.codex/models_cache.json`의 공개 항목을 읽습니다. Codex가 목록을 갱신하면 다음 customization에서 새 모델도 표시됩니다. 캐시를 읽을 수 없으면 Luna/Sol 외에 Astra, GPT-6 Sol, GPT-5.6 Sol/Terra/Luna, GPT-5.5를 포함한 내장 목록을 표시합니다.

사용할 수 없는 모델이나 effort에서는 실패 증거를 남기고 종료합니다. 목록은 계정의 실행 권한을 보장하지 않으며 캐시가 오래됐을 수 있습니다. Model 메뉴의 `c`로 custom model ID도 입력할 수 있습니다. 지원 reasoning 정보가 있으면 안내하며 effort는 사용자가 선택합니다. 모델이나 effort를 자동 대체하지 않습니다. Non-TTY에서 Task를 생략하면 usage error로 종료합니다.

TTY에서는 현재 Role, model, reasoning, elapsed, validation 실패, repair 횟수와 최종 Exec 경로를 stderr에 표시합니다. Direct mode의 stdout 최종 JSON은 유지됩니다.

## 실행 기록

~~~text
<target>/.codex-devflow/runs/<run-id>/
  task.json
  analysis.json
  plan.json / plan.md
  baseline.json / baseline.diff / changes.diff
  steps/<step>/prompt.txt, schema.json, response.json, stdout.log, stderr.log, result.json
  validation/<attempt>/<command>/stdout.log, stderr.log
  validation.json / review.json / repair.json
  run.json / exec.md
~~~

`analysis`와 `plan.json`은 해당 단계가 성공했을 때 생성됩니다. Simple 경로의 `plan.md`에는 생략 사유가 기록됩니다. 실패 또는 중단 시 마지막 단계와 남아 있는 evidence를 최종 기록에 보존합니다.

Changed files는 실행 전후 내용·파일 모드 snapshot으로 계산합니다. `changes.diff`에는 기존 working tree 변경도 포함되며, `baseline.diff`로 시작 상태를 확인할 수 있습니다. `.codex-devflow/`를 target의 `.gitignore`에 추가하는 것을 권장합니다. 로그에는 task와 코드가 포함되므로 공유 전에 내용을 확인하세요.

## 현재 범위

현재 구현에는 역할별 모델 정책과 interactive terminal UX, 로컬 CLI, Codex backend abstraction, versioned structured analysis/review, 두 경로의 routing, Plan/Exec, shell validation, bounded repair, 실행 시간과 CLI가 노출한 usage 기록이 포함됩니다.

한 저장소에서는 한 run씩 실행합니다. 종료된 run의 resume은 지원하지 않습니다. DevFlow는 push·PR 생성·merge·branch 삭제·파괴적 DB 작업을 실행 단계로 제공하지 않으며, Codex prompt에도 해당 동작을 금지합니다. 이 경계는 CLI sandbox와 prompt에 의존합니다.

전문 review, 병렬 worker, native subagent, API backend, eval harness는 [Roadmap](docs/ROADMAP.md)의 후속 단계입니다.

## 검증과 평가

~~~bash
python3 -m unittest discover -s tests -v
~~~

테스트는 fake Codex executable과 임시 Git 저장소로 routing, structured output, subprocess 실행, timeout, repair, 중단, artifact를 확인합니다. 실제 Codex 실행과 요구사항별 검증 결과는 [001 실행 기록](docs/exec/001-initial-implementation.md)과 [002 실행 기록](docs/exec/002-worker-role-model-interactive-ux.md)에 정리합니다.

생산성·품질·비용 개선은 비교 실험으로 확인할 가설입니다. V0는 elapsed time, Codex 실행 횟수, validation/repair 횟수와 CLI가 노출한 usage를 기록합니다. Direct Codex와의 비교 평가는 [평가 전략](docs/EVALUATION.md)을 따릅니다.

## 문서

- [사용자 매뉴얼](docs/MANUAL.md)
- [PRD](docs/PRD.md)
- [프로젝트 정의](docs/PROJECT.md)
- [아키텍처](docs/ARCHITECTURE.md)
- [첫 번째 구현 계획](docs/plans/001-initial-implementation.md)
- [001 실행 기록](docs/exec/001-initial-implementation.md)
- [002 구현 계획](docs/plans/002-worker-role-model-interactive-ux.md)
- [002 실행 기록](docs/exec/002-worker-role-model-interactive-ux.md)
- [왜 Codex DevFlow인가](docs/WHY.md)
- [Roadmap](docs/ROADMAP.md)
- [공식 레퍼런스](docs/REFERENCES.md)

## License

MIT License.
