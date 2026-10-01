# 001 초기 구현 실행 기록

## 결과

기존 설계 문서와 001 계획에서 PRD를 정리한 뒤 Python 표준 라이브러리 기반 V0를 구현했다. 실제 로그인된 Codex CLI의 planned workflow가 코드 수정, validation, General Review, 최종 기록까지 성공했다. 001 Definition of Done을 충족했다. 검증일은 2026-10-01(KST)이다.

## 실제 변경

- `docs/PRD.md`: R1–R10 요구사항, 수용 기준, V0 경계 정의.
- `codex_devflow/`: CLI/config, backend abstraction, Codex CLI 실행, versioned schema, simple/planned routing, validation, bounded repair, Git evidence, artifact 생성.
- `pyproject.toml`, `.codex-devflow.json`, `.gitignore`: 설치 진입점, 이 저장소의 검증 명령, 로컬 artifact 제외.
- `tests/`: fake Codex executable, 임시 Git 저장소, 실제 subprocess와 signal을 사용하는 단위·통합 테스트.
- `README.md`: 부정 후 대조하는 표현을 정리하고 설치·실행·설정·종료 상태·artifact를 구현 기준으로 설명.
- `docs/ARCHITECTURE.md`, `docs/EVALUATION.md`: 실제 구현과 측정 가능한 값, 후속 범위 구분.

## 계획 대비 변경점

001에서 미확정이던 언어는 Python 3.11+, 명령은 `codex-devflow`, artifact 위치는 target의 `.codex-devflow/runs/<run-id>/`로 확정했다. 실행 runtime dependency는 없다. JSON 설정과 CLI override를 사용하며 API client를 추가하지 않았다.

Plan뿐 아니라 구현 결과도 structured JSON으로 받아 변경 요약·계획 대비 변경점·제한을 최종 Exec에 포함한다. Exec 자체는 deterministic code로 생성한다. 두 경로와 General Review 하나를 구현했다.

실제 실행에서 중단 시 subprocess 결과가 유실되는 문제를 발견해 validation과 Codex worker의 중단 evidence 보존을 보완했다. SIGINT·SIGTERM 통합 테스트를 추가했다. 같은 repository의 동시 run은 lock으로 차단한다.

## 검증 결과

환경: macOS, Python 3.12.1, Codex CLI 0.158.0, ChatGPT 로그인.

| 검증 | 실제 결과 |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 최종 27개 통과, 테스트 보고 시간 16.587초, exit 0 |
| wheel 빌드 및 임시 venv 설치 | `pip install --no-index --no-build-isolation --no-deps` 성공 |
| 설치된 `codex-devflow`를 `/tmp`에서 실행 | 임시 Git 저장소 + fake executable로 planned workflow succeeded, exit 0 |
| 실제 Codex planned workflow | succeeded, 156.806초, Codex 4회, validation 1회, repair 0회 |
| 실제 deterministic validation | 27개 테스트 통과, process elapsed 15.605초, exit 0 |
| 실제 General Review | passed=true, findings=[] |
| artifact 직접 확인 | 필수 파일 존재, schema 유효, run과 단계별 JSON 일치, stdout/stderr 파일 존재 확인 |

실제 task는 **repair worker가 오류 또는 중단으로 종료될 때 repair 상태가 started로 남는 버그 수정**이다. 변경 파일은 `codex_devflow/workflow.py`, `tests/test_devflow.py` 두 개다. 오류·중단 상태와 원인을 repair history에 보존하고, completed repair는 유지하도록 수정했다. 회귀 테스트로 repair 상한, 이후 단계 미실행, repair.json/run.json/exec.md 일치를 확인했다.

실제 run ID: `20261001T011842Z-ebb34fa776`. 원 task, analysis, plan, validation, review, repair history, 원형 usage, artifact hash는 [검증 증거](001-verification.json)에 저장했다. [최종 테스트 출력](001-tests.txt)도 보존한다. 전체 로컬 raw evidence는 `.codex-devflow/runs/20261001T011842Z-ebb34fa776/`에서 확인한다. 이 디렉터리는 Git ignore 대상이다.

실제 성공 run에서는 repair가 필요하지 않았다. Repair 성공·review 실패·한도 소진·repair 중 오류/중단은 fake backend 기반 통합 테스트로 검증했다. 실제 모델이 repair까지 수행한 성공 run으로 해석하지 않는다.

최종 재검증 전에는 이전 중단 실행이 남긴 사용하지 않는 fake worker 시나리오를 제거했다. 제품 코드는 실제 성공 run 이후 추가 변경하지 않았다.

### 실패 실행도 보존

| Run | 상태/단계 | 관측 결과 |
| --- | --- | --- |
| `20260930T191646Z-492cd44841` | error / analyze | 제한된 외부 sandbox에서 Codex app-server 초기화 Operation not permitted |
| `20260930T191719Z-87b45e1156` | error / implement | 단계별 240초 timeout; process/workflow/tests의 일부 수정은 보존. worker 내부 테스트의 ps 호출도 권한 오류 발생 |
| `20260930T192432Z-22f508272b` | error / implement | 계정 usage limit, exit 1. ps 의존성 제거와 worker 중단 기록 수정은 저장됐으며 후속 직접 테스트 25개 통과 |
| `20261001T011842Z-ebb34fa776` | succeeded / review | 600초 설정, 모든 단계 및 27개 테스트 통과 |

초기 fake 테스트에서 Python cache 파일도 변경으로 집계된 것을 확인했다. 변경 수집은 정상 동작한 것이며, 테스트 validation에 `-B`를 사용해 불필요한 cache 생성을 막았다.

## 발견한 제한

- Codex 내부 sandbox에서 또 다른 Codex CLI를 실행하면 초기화가 권한 오류로 실패할 수 있다. 실제 end-to-end 검증은 정상 호스트 권한에서 수행하고 각 worker의 read-only/workspace-write sandbox는 유지했다.
- 작업별 실행 시간이 달라진다. 240초 제한의 구현 단계는 시간 초과됐으며 다음 run에는 기본값인 600초를 적용했다. 실패 run도 기록에 포함한다.
- Codex 계정의 usage limit으로 구현 worker가 exit 1로 종료된 run도 있었다. 일부 수정은 저장됐지만 workflow 성공으로 기록하지 않았다. 계정 제한 해제 후 새 run으로 검증을 계속했다.
- `ps` 기반 프로세스 확인이 sandbox에서 차단되는 것을 확인했다. 중단 테스트는 외부 프로세스 목록 명령을 사용하지 않도록 수정했다.
- Usage는 CLI가 노출한 이벤트만 기록한다. 중단된 실행에서 누락될 수 있으며 비용·credit으로 환산하지 않는다.
- Validation/review 통과와 사용자의 최종 task 수용은 구분한다. Direct Codex 비교 실험, 생산성·비용 개선 평가는 수행하지 않았다.
- POSIX/macOS에서 검증했다. Windows, resume, SIGKILL 이후 최종화, 다른 도구와의 동시 편집 격리, ignored 파일 및 submodule 내부 변경의 완전한 추적은 현재 범위 밖이다.
- Snapshot과 diff는 로컬 파일을 읽는다. 대규모 저장소의 메모리·context 사용량은 별도 검증하지 않았다.

## 후속 작업

Usage limit의 구체적인 사유가 raw log에만 남았던 관측을 근거로 [003 실행 오류 원인 전달 계획](../plans/003-runtime-error-reporting.md)을 작성했다. 제안 상태이며 구현하지 않았다.

실제 개인 프로젝트 task에서 현재 설정과 run evidence를 관찰하고 실패 종류·elapsed·repair 횟수를 축적한다. 전문 review나 병렬 실행은 Roadmap의 다음 단계에서 필요성을 확인한 뒤 별도 계획으로 다룬다. 이번 구현에는 추가하지 않았다.


## 요구사항별 확인 항목

| PRD | 확인 방법 |
| --- | --- |
| R1 | 모듈 CLI, 설치된 console script, project config/CLI override와 종료 코드 테스트 |
| R2 | 실제 로그인된 Codex CLI, fake executable의 오류·timeout·JSON 검사, stdout/stderr와 process result 보존 |
| R3 | versioned analysis schema의 enum/타입/필수 필드 검사와 실제 Scout artifact |
| R4 | local/low risk simple, 각 위험 flag 및 unknown planned routing 테스트 |
| R5 | 실제 plan과 구현 prompt, Plan의 필수 항목과 변경 파일 확인 |
| R6 | 다중 명령, nonzero exit, timeout, unavailable, 출력 증거 확인 |
| R7 | General Review에 원 task/plan/diff/validation 전달 및 structured review 확인 |
| R8 | validation 실패 후 복구, review 실패 후 복구, 한도 소진, 0회 repair 테스트 |
| R9 | 성공·실패·중단 artifact, baseline 보존, SIGINT/SIGTERM과 자식 heartbeat 종료, 중단 명령 결과 일치 |
| R10 | backend sandbox 옵션 테스트와 workflow의 push/merge 실행 단계 부재; prompt 정책과 실제 권한 경계는 구분 |
