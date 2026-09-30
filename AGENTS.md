# Repository Instructions

## 목적

이 저장소는 Codex CLI를 첫 execution backend로 사용하는 로컬 개발 orchestration 도구 Codex DevFlow를 구현합니다.

구조를 변경하기 전에 다음 문서를 우선 확인합니다.

- docs/PROJECT.md
- docs/ARCHITECTURE.md
- docs/EVALUATION.md
- docs/plans/001-initial-implementation.md

## 개발 원칙

1. 첫 구현은 local-first로 유지합니다.
2. 별도 계획 없이 OpenAI API 직접 연동을 추가하지 않습니다.
3. Codex 실행은 내부 backend abstraction 뒤에 둡니다.
4. workflow state, retry limit, timeout, process execution, artifact path, metric 수집은 가능한 한 deterministic code로 처리합니다.
5. repository 분석, 요구사항 해석, 계획, 구현, 진단, engineering review는 Codex가 담당할 수 있습니다.
6. 독립 실행이나 context isolation의 실질적 이점이 없으면 Subagent를 추가하지 않습니다.
7. 측정되지 않은 생산성, 품질, token, 비용 개선을 주장하지 않습니다.
8. 초기 버전은 target repository의 push 또는 merge를 자동 승인하지 않습니다.

## Plan / Exec 규칙

복잡한 기능이나 큰 refactor를 구현할 때는 docs/plans 아래에 계획을 먼저 작성합니다.

계획에는 최소한 다음을 포함합니다.

- 문제
- 현재 동작
- 목표 동작
- 영향 컴포넌트
- 구현 순서
- 검증 방법
- 위험과 미확정 사항

구현과 검증이 끝나면 docs/exec 아래에 실제 실행 결과를 남깁니다.

Exec 문서는 최초 계획을 그대로 복사하지 않고 다음을 구분합니다.

- 실제 변경
- 계획 대비 변경점
- 검증 결과
- 발견한 제한
- 후속 작업

단순 문서 수정이나 명확한 소규모 변경은 Plan을 강제하지 않습니다.

## 문서 규칙

구현되지 않은 기능을 이미 존재하는 것처럼 서술하지 않습니다. 동작이 바뀌면 관련 Architecture 또는 Evaluation 문서도 함께 갱신합니다.
