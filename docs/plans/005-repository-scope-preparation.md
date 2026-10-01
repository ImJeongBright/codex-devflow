# 005 — Repository 범위와 준비 단계 표시

## 문제와 현재 동작

사용자가 `--repo ~/Documents/dbms`로 실행했지만 그 폴더에는 `.git`이 없고 Git 루트가 `~/Documents`였다. DevFlow가 자동으로 상위 루트를 사용해 snapshot/diff 수집을 오래 수행했다. 첫 worker 시작 전에는 진행 표시와 run.json이 없었고, 준비 도중 중단하면 최종 evidence 수집을 다시 시도할 수 있었다.

## 목표 동작

- 사용자가 지정하거나 현재 디렉터리로 선택한 폴더가 Git 루트와 다르면 run 생성 전에 명확한 오류로 종료한다. 작업 범위를 상위 폴더로 확장하지 않는다.
- Repository 준비 시작/완료를 progress에 표시하고 준비 시작 전에 run.json의 stage를 기록한다.
- Worker를 시작하지 못한 실행은 최종화 과정에서 파일 수집을 다시 수행하지 않고 제한을 기록한다.
- DBMS 폴더에는 독립 Git metadata를 생성해 실제 작업 범위를 복구한다. 상위 Documents 저장소와 기존 파일은 보존한다.

## 영향 컴포넌트

repository.root, Workflow 준비/최종화, TerminalProgress, Manual/Architecture/Exec. DBMS의 Git metadata와 로컬 artifact/build ignore 설정.

## 구현 순서

1. Git 루트, run artifact와 정확한 실행 process를 확인한다.
2. 잘못된 범위의 실행을 중단하고 DBMS Git 루트를 분리한다.
3. Git 루트 일치 검사와 준비 checkpoint/progress를 추가한다.
4. 첫 worker 이전 실패의 evidence 재수집을 방지하고 문서에 변경을 기록한다.

## 검증 방법

실제 DBMS의 Git 루트를 확인하고 중단한 process의 종료를 확인한다. 코드 경로, AST 구문, diff whitespace와 문서 링크를 확인한다. 이번 요청에는 자동 테스트 실행 지시가 없어 테스트 추가/실행과 실제 model workflow 재실행은 하지 않는다.

## 위험과 미확정 사항

Git 하위 디렉터리를 전달하면 이제 거부된다. 전체 repository 작업이 의도라면 정확한 루트 경로를 사용해야 한다. Symlink와 macOS 경로 대소문자는 samefile로 같은 물리적 디렉터리인지 확인한다. 큰 저장소의 evidence 수집 자체를 제한하거나 timeout을 적용하는 기능은 이번 범위에 포함하지 않는다.
