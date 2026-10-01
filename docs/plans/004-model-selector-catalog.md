# 004 — 모델 선택 목록 확장

## 문제

사용자가 Luna와 Sol 외의 모델도 메뉴에서 선택할 수 있어야 한다고 요청했다. 002의 custom ID 입력은 유지하되, 모델 이름을 직접 알아야 하는 부담을 줄인다.

## 현재 동작

`MODEL_PRESETS`의 두 모델만 번호 선택 메뉴에 표시한다. Custom ID와 CLI/config override로 다른 모델을 지정할 수 있다. 기본 Role 정책과 sandbox는 별도로 고정되어 있다.

## 목표 동작

- Codex의 로컬 `models_cache.json`에서 UI 표시용 모델을 읽어 메뉴에 모두 표시한다. `$CODEX_HOME`이 있으면 해당 경로, 없으면 `~/.codex`를 사용한다.
- `visibility=list`만 표시하고 숨김·잘못된 항목·중복 ID를 제외한다. 현재 두 기본 모델이 있으면 기존 번호 1/2를 유지하고 나머지 모델을 목록 순서로 추가한다.
- 캐시가 없거나 읽을 수 없으면 확장된 내장 목록과 출처 안내를 표시한다. 캐시의 정상적인 빈 목록은 custom ID 입력 경로를 제공한다.
- 모델 표시 이름과 실제 ID를 함께 보여 주고 선택한 ID를 기존 WorkerPolicy로 전달한다. 지원 reasoning 정보가 있으면 선택 전에 안내한다.
- 기존 Role defaults, permission, override/저장, custom ID와 no execution fallback 정책을 유지한다.

## 영향 컴포넌트

`roles.py`의 내장 목록, 로컬 catalog reader, terminal model 메뉴, README/Manual/Architecture, 실행 기록.

## 구현 순서

1. 설치된 Codex의 로컬 cache 형식과 공개 모델 항목을 확인한다.
2. 외부 API 호출 없이 cache를 읽는 catalog adapter를 추가한다.
3. 모델 menu에 catalog와 표시 이름/ID를 연결하고 출처를 안내한다.
4. 문서를 갱신하고 실제 변경과 확인 결과를 Exec에 기록한다.

## 검증 방법

변경 diff와 로컬 cache의 표시 항목을 대조한다. 모델 선택과 역할 정책 전달, 오류/빈 catalog의 처리 경로를 확인한다. 이번 추가 요청에는 테스트 실행 지시가 없으므로 자동 테스트 추가·실행은 하지 않는다. 002 테스트 결과는 이전 구현의 검증으로 유지한다.

## 위험과 미확정 사항

Codex cache는 내부 파일 형식이며 버전에 따라 달라질 수 있다. Stale cache와 내장 목록은 현재 계정의 모델 사용 권한을 보장하지 않는다. Codex CLI가 갱신한 목록을 다음 customization에 반영하며 DevFlow가 인증/직접 모델 API 호출/캐시 갱신을 추가하지 않는다. Reasoning 메뉴의 기존 preset은 유지하고 모델별 지원 정보는 안내로 제공한다.

## 완료 조건

두 모델 외의 공개 Codex 모델을 번호로 선택할 수 있고 custom ID가 유지된다. 숨김 모델과 중복을 메뉴에 표시하지 않는다. 캐시 오류가 workflow 입력을 막지 않는다. Role defaults와 backend 전달은 유지되며 실제 변경과 한계를 Exec에 기록한다.
