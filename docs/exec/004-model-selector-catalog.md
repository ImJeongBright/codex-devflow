# 004 — 모델 선택 목록 확장 실행 기록

## 실제 변경

[004 계획](../plans/004-model-selector-catalog.md)에 따라 Model 메뉴의 두 모델 제한을 해제했다.

- `catalog.py`는 `$CODEX_HOME/models_cache.json`, 미설정 시 `~/.codex/models_cache.json`을 읽는다. `visibility=list` 모델의 표시 이름/실제 ID를 사용하고 숨김·중복·잘못된 ID를 제외한다.
- 기존 Luna/GPT-6.1 Sol 번호는 해당 항목이 있을 때 1/2로 유지하고 나머지 공개 모델을 추가한다. 메뉴는 모델별 한 줄에 이름과 ID를 표시한다.
- 캐시가 없거나 읽기/형식 오류가 있으면 8개 내장 모델 목록과 출처를 표시한다. 정상적인 빈 목록은 custom ID 경로를 유지한다.
- Customization마다 캐시를 다시 읽는다. 지원 reasoning metadata가 있으면 안내하고 현재 effort가 목록에 없으면 선택을 요청하는 안내를 표시한다. Enter는 기존 effort를 유지한다.
- README, Manual, Architecture에 목록 출처, 선택 방법과 캐시 한계를 기록했다. Role default/sandbox/backend 전달/실행 실패 정책은 변경하지 않았다.

## 계획 대비 변경점

없음. API 모델 목록을 그대로 붙이거나 새 provider를 추가하지 않았다. 로컬 CLI가 사용하는 목록을 읽고 사용자가 custom ID를 계속 지정할 수 있도록 했다. 직접 API 호출, 인증 관리, app-server 통신이나 자동 cache refresh는 추가하지 않았다.

## 확인 결과

2026-10-01 로컬 cache의 형식을 직접 확인했다. `models` 항목은 10개였으며 표시용 모델은 다음 8개였다. 숨김 항목 2개는 일반 선택 목록에서 제외하도록 구현했다. Cache의 identity 및 prompt/instructions는 문서나 제품 출력에 복사하지 않았다.

| 메뉴 번호 | Model ID |
| --- | --- |
| 1 | gpt-6-luna |
| 2 | gpt-6.1-sol |
| 3 | gpt-6-astra |
| 4 | gpt-6-sol |
| 5 | gpt-5.6-sol |
| 6 | gpt-5.6-terra |
| 7 | gpt-5.6-luna |
| 8 | gpt-5.5 |

코드 diff에서 모델 목록의 입력·visibility 필터·중복 제거·ID 검사·선택된 ID의 저장 경로와 기존 정책 전달 경계를 확인했다. Python AST 구문 검사, 로컬 Markdown 링크와 whitespace 검사를 수행했다. 이번 추가 요청에는 테스트 실행 지시가 없어 자동 테스트를 추가하거나 실행하지 않았다. 002의 50개 테스트 결과는 변경 전 버전의 기록이며 이번 변경의 회귀 검증으로 주장하지 않는다. 실제 모델별 inference도 실행하지 않았다.

## 발견한 제한

모델 목록은 cache 시점과 Codex 버전에 영향을 받으며 계정 권한 확인 결과가 아니다. 공개 문서도 app-server의 bundled/cached catalog와 실제 inference 접근 확인을 구분한다. [공식 Codex app-server 문서](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server).

캐시의 내부 형식이 바뀌면 내장 목록을 사용할 수 있다. 내장 목록도 현재 사용 가능성을 보장하지 않는다. API 전용/다른 provider 모델은 custom ID 입력 경로를 사용하며 실제 실행 가능 여부는 Codex CLI에 따른다. Reasoning 메뉴는 기존 preset을 유지한다. 지원하지 않는 model/effort 조합을 지정하면 자동 대체 없이 실패한다.

## 후속 작업

Codex cache 형식이 바뀌면 parser와 내장 목록을 갱신한다. 캐시/빈 목록/오류/선택의 회귀 테스트와 실제 PTY 검증은 다음 테스트 요청 때 수행한다.
