# 의미 검증 레이어 개선 전후 비교 리포트

- 생성 시각: 2026-06-22 17:59:55
- 작업 브랜치: `meaning-validation-layer`
- 복구 기준: `main` 브랜치의 기존 안정 상태 또는 baseline 리포트 파일
- 검정 범위: 30개 단어 x 3개 오류 유형 = 90개 문장
- 실행 모드: 비용 안전 모드(LLM API 호출 비활성화)

## 결론

- 전체 PASS가 `32/90`에서 `89/90`로 개선되었습니다.
- 개선 케이스는 `57`건, 회귀 케이스는 `0`건입니다.
- 타겟 감지와 문법 판정은 최종 기준 90/90입니다.
- 의미 판정은 최종 기준 89/90이며, 남은 1건은 `애틋하다`의 복합 의미 오용 케이스입니다.

## 전체 지표 비교

| 항목 | 개선 전 | 개선 후 | 변화 |
| --- | ---: | ---: | ---: |
| 전체 PASS | 32/90 (35.6%) | 89/90 (98.9%) | +57 |
| 타겟 감지 PASS | 90/90 (100.0%) | 90/90 (100.0%) | +0 |
| 문법 판정 PASS | 90/90 (100.0%) | 90/90 (100.0%) | +0 |
| 의미 판정 PASS | 32/90 (35.6%) | 89/90 (98.9%) | +57 |

## 오류 유형별 비교

| 오류 유형 | 개선 전 PASS | 개선 후 PASS | 변화 |
| --- | ---: | ---: | ---: |
| 의미 오류 | 1/30 | 30/30 | +29 |
| 문법 오류 | 30/30 | 30/30 | +0 |
| 문법+의미 오류 | 1/30 | 29/30 | +28 |

## 구현한 개선 내용

- `meaning_profiles.json`을 추가해 seed 단어, KRDICT/우리말샘 accepted 문서, seed 예문, 제외 의미를 단어별 프로필로 묶었습니다.
- `validate_meaning.py`를 추가해 문장 맥락의 물리 속성/제외 의미/금지 맥락을 profile 기반으로 탐지합니다.
- `generate_feedback.py`에서 LLM 응답 또는 fallback 결과보다 profile 기반 의미 오류 판정이 강하면 `meaning.correct=false`로 덮어쓰게 했습니다.
- 정확 타겟 단어 사전 근거는 Chroma metadata에서 먼저 조회하도록 해 불필요한 쿼리 임베딩 호출을 줄였습니다.
- `챙기다`, `신경 쓰다`의 활용형 감지를 보강했습니다.

## 남은 실패 케이스

| # | 단어 | 유형 | 문장 | 기대(G/M) | 실제(G/M) |
| ---: | --- | --- | --- | --- | --- |
| 72 | 애틋하다 | 문법+의미 오류 | 계산기 버튼을 쫒는 감정이 애틋하다. | False/False | False/True |

## 복구 방법

- 현재 개선 작업은 `meaning-validation-layer` 브랜치에서 진행했습니다.
- 기존 형태로 돌아가려면 `main` 브랜치로 전환하면 됩니다.
- 비교 기준 baseline 파일은 아래에 보존되어 있습니다.
- `ieung_service/reports/functional_validation_30_words_90_cases_baseline.md`
- `ieung_service/reports/functional_validation_30_words_90_cases_baseline.json`

## 산출물

- 개선 후 상세 리포트: `ieung_service/reports/functional_validation_30_words_90_cases.md`
- 개선 후 raw 결과: `ieung_service/reports/functional_validation_30_words_90_cases.json`
- 비교 리포트: `ieung_service/reports/meaning_validation_comparison_report.md`
