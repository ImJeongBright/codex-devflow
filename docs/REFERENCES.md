# 공식 레퍼런스

Codex와 OpenAI 제품 동작은 바뀔 수 있으므로 구현 전에 공식 문서를 다시 확인합니다.

## ChatGPT 플랜에서 Codex 사용

https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan

이 프로젝트와 관련된 핵심:

- ChatGPT 계정으로 Codex에 로그인할 수 있습니다.
- 해당 경우 ChatGPT 플랜의 Codex allowance / credit을 사용합니다.
- 직접 API Key를 사용하면 API pricing이 적용됩니다.

따라서 첫 DevFlow는 별도 OpenAI API client 없이 Codex CLI를 실행 backend로 사용할 수 있습니다.

## AGENTS.md

https://developers.openai.com/api/docs/guides/latest-model

Codex CLI는 repository 경로의 AGENTS.md 지침을 읽을 수 있습니다.

프로젝트별 지속적인 개발 규칙은 매 Task prompt에 반복하기보다 AGENTS.md로 관리할 수 있습니다.

## ExecPlan

https://developers.openai.com/cookbook/articles/codex_exec_plans

복잡한 기능과 큰 refactor에서 명시적인 execution plan을 사용하는 패턴입니다.

DevFlow의 planned workflow 설계에 참고합니다.

## Skills

https://developers.openai.com/api/docs/guides/tools-skills

Skill은 반복 가능한 지침과 supporting file을 묶습니다.

DevFlow에서는 database review, reliability review, execution documentation 같은 procedure에 사용합니다.

## Skill Eval

https://developers.openai.com/blog/eval-skills

Codex 실행 결과를 artifact, check, score로 체계적으로 평가하는 방법을 참고합니다.

특히 structured output을 사용하면 여러 Run을 프로그램으로 비교하기 쉽습니다.

## Agents

https://developers.openai.com/api/docs/guides/agents

향후 더 높은 수준의 orchestration, tool, MCP, multi-agent가 필요할 때 참고합니다.

초기 DevFlow는 이 복잡도를 먼저 도입하지 않고 local Codex CLI backend부터 검증합니다.
