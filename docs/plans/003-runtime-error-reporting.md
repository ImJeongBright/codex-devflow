# 실행 오류 원인 전달 보완 계획

상태: 제안, 미구현. 001의 실제 실패 기록에서 도출한 후속 계획이다.

## 문제

001 실행 중 Codex usage limit이 발생했다. JSONL에는 구체적인 사유가 있었지만 최종 CLI 요약에는 `Codex process exited with 1`만 표시돼 raw log를 열어야 원인을 알 수 있었다.

근거 run: `20260930T192432Z-22f508272b`. [001 실행 기록](../exec/001-initial-implementation.md)을 참고한다.

## 현재 동작

Backend는 exit code, timeout, structured output 오류를 정규화한다. Codex JSONL의 error/turn.failed 메시지는 raw stdout에 보존한다.

## 목표 동작

실행 실패 시 CLI가 노출한 원인 메시지를 normalized error와 최종 run 기록에서 확인할 수 있게 한다. 자동 재시도나 별도 인증 관리 기능은 추가하지 않는다.

## 영향 컴포넌트

`codex_devflow/backend.py`, backend 통합 테스트, Architecture 및 Exec 문서.

## 구현 순서

1. 보존된 실패 JSONL의 메시지 형식을 확인한다.
2. 알려진 오류 이벤트를 추출하고 없으면 현재 exit code 메시지를 유지한다.
3. 오류 메시지 크기와 기록 범위를 정한다.
4. fixture 기반 회귀 테스트와 실제 보존 로그 재생으로 검증한다.

## 검증 방법

Usage limit, 일반 turn.failed, 비정형 stdout, 메시지 없는 nonzero exit, timeout, 성공 응답을 검증한다. 원인 전달이 workflow routing·repair 횟수·종료 코드를 바꾸지 않아야 한다.

## 위험과 미확정 사항

CLI 이벤트 형식은 버전에 따라 달라질 수 있다. 메시지에 로컬 경로나 민감한 값이 포함될 수 있으므로 표시·보존 범위를 구현 전에 정한다. 이 계획은 001 제품 기능에 아직 반영하지 않았다.
