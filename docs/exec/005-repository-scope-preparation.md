# 005 — Repository 범위와 준비 단계 실행 기록

## 실제 변경

[005 계획](../plans/005-repository-scope-preparation.md)에 따라 Git 루트가 사용자가 선택한 프로젝트 폴더와 다르면 실행을 거부하도록 바꿨다. samefile로 경로 대소문자/symlink를 처리한다. 에러에는 요청 경로와 발견한 Git 루트, 정확한 루트를 선택하거나 별도 repository로 초기화하라는 안내를 표시한다.

첫 snapshot/diff 이전에 run.json의 prepare stage를 기록하고 TTY에 Repository evidence 준비 시작/완료를 표시한다. Worker를 시작하지 못한 실행은 최종화에서 Git evidence 수집을 다시 수행하지 않고 제한을 남긴다. 기존 worker policy, workflow routing, validation/repair와 timeout 설정은 유지한다.

사용자가 보고한 DBMS 실행은 정확한 PID/command를 재확인한 후 SIGINT로 중단했다. 첫 중단 후에도 최종 evidence 수집이 진행되어 두 번째 SIGINT를 전달했고 process 종료를 확인했다. DBMS 폴더에 독립 .git metadata를 만들었다. 로컬 artifact·실행 binary·debug bundle·DB 파일·Python cache를 제외하는 .gitignore 항목을 추가하며 기존 내용을 보존했다. 상위 Documents repository와 DBMS 소스 파일은 수정하거나 삭제하지 않았다.

## 계획 대비 변경점

없음. Repository 수집의 크기/시간 상한, 자동 모델 재시도나 DBMS 기능 구현은 추가하지 않았다. Git 하위 폴더를 받던 기존 CLI 동작은 더 엄격해졌으며 Manual/Architecture/README에 기록했다.

## 확인 결과

2026-10-01 사용자 보고 시 DBMS의 Git 루트는 `/Users/jeonjeonghyeon/Documents`였다. PID 44655의 정확한 command는 DBMS를 --repo로 받은 DevFlow 실행이었다. 실행 시간 20분 19초, state R+를 관측했다. 두 run directory에는 task.json만 있고 run.json/worker artifact는 없었다. 코드 실행 순서와 대조하면 첫 Codex worker 이전의 snapshot/diff 준비 단계에 있었다. Snapshot과 diff 중 어느 함수에서 시간을 소비했는지는 stack trace로 확인하지 않았다.

중단 후 PID 44655의 종료를 확인했다. 독립 Git 초기화 후 `git rev-parse --show-toplevel`은 `/Users/jeonjeonghyeon/Documents/dbms`를 반환했다. 해당 폴더의 Git 파일 목록은 DBMS 소스·문서와 보조 예제 폴더로 제한됐다. 다른 Documents 파일 내용은 조사하거나 실행 기록에 포함하지 않았다.

Python AST 구문 검사, 로컬 문서 링크와 diff whitespace를 확인했다. 이번 장애 보고에는 자동 테스트 실행 지시가 없어 테스트를 추가하거나 실행하지 않았다. DBMS 기능 workflow도 재실행하지 않았으며 모델 실행 성공을 주장하지 않는다.

## 발견한 제한

기존 준비 단계는 worker timeout과 별개였다. 이번 변경은 범위 검사와 준비 표시를 추가하고 첫 worker 이전 실패의 중복 수집을 방지한다. 사용자가 의도적으로 지정한 대규모 Git 루트의 수집 비용은 여전히 발생할 수 있다.

중단한 실행은 변경 전 버전이며 준비 단계의 run.json checkpoint가 없어 task.json만 남았다. 원 실행 기록을 성공으로 바꾸거나 소급 생성하지 않았다. Documents의 `.codex-devflow`도 삭제하지 않았다.

DBMS에 기존 Python unittest 디렉터리는 확인되지 않았다. `unittest discover`는 테스트가 0개여도 성공할 수 있으므로 다음 task에는 회귀 테스트 작성 요구를 함께 전달해야 한다.

## 후속 작업

명시적 Git 루트/하위 폴더/worktree/symlink, preparation event와 실패/중단 시 재수집 생략에 대한 회귀 테스트는 다음 테스트 요청 때 수행한다. 큰 저장소의 evidence 크기/시간 제한이 필요하면 별도 계획으로 다룬다.
