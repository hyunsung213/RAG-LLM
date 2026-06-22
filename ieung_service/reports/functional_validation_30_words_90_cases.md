# 30개 문화어휘 기능 검정 리포트

- 생성 시각: 2026-06-22 17:59:12
- 검정 범위: 30개 단어 x 3개 오류 유형 = 90개 문장
- 실행 모드: 비용 안전 모드(LLM API 호출 비활성화, 사전 metadata 조회 + fallback/후처리 로직 검정)
- 판정 기준: target_word, grammar.correct, meaning.correct가 기대값과 모두 일치하면 PASS

## 요약

| 항목 | 결과 |
| --- | ---: |
| 전체 케이스 PASS | 89/90 (98.9%) |
| 타겟 단어 감지 PASS | 90/90 (100.0%) |
| 문법 판정 PASS | 90/90 (100.0%) |
| 의미 판정 PASS | 89/90 (98.9%) |

## 오류 유형별 결과

| 오류 유형 | PASS | Target | Grammar | Meaning |
| --- | ---: | ---: | ---: | ---: |
| 의미 오류 | 30/30 | 30/30 | 30/30 | 30/30 |
| 문법 오류 | 30/30 | 30/30 | 30/30 | 30/30 |
| 문법+의미 오류 | 29/30 | 30/30 | 30/30 | 29/30 |

## 주요 발견

- 타겟 단어 감지는 90/90로 확인되었습니다.
- 문법 판정은 90/90로 확인되었습니다. 공통 표기 오류 `쫒` -> `쫓`를 포함해 현재 후처리 규칙에서 안정적으로 잡힙니다.
- 의미 판정은 89/90로 확인되었습니다. meaning profile 기반 검증 레이어가 일반 의미 오용 대부분을 잡습니다.
- 실행 모드는 비용 안전 모드입니다. 실제 Gemini 호출을 켠 운영 환경과 결과가 일부 다를 수 있습니다.

## 개선 권장사항

1. seed의 `brief_meaning`과 사용자 문장의 핵심 서술어를 비교하는 일반 의미 검증 레이어를 추가합니다.
2. `meaning.correct=true`를 fallback 기본값으로 두지 말고, 사전 근거가 있어도 문맥 적합성 판단이 불확실하면 `review_needed` 성격의 상태를 둘지 검토합니다.
3. 문법 검증은 현재 특정 표기 오류 중심이므로 조사 오류, 띄어쓰기, 활용 오류 규칙을 단어별로 확장합니다.
4. 운영 품질 검정은 별도 승인 후 Render `/feedback` 엔드포인트에 대해 live LLM 모드로 90개를 한 번 더 실행하는 것이 좋습니다.

## 단어별 PASS 요약

| 단어 | PASS | 의미 오류 | 문법 오류 | 문법+의미 오류 |
| --- | ---: | --- | --- | --- |
| 정 | 3/3 | PASS | PASS | PASS |
| 서운하다 | 3/3 | PASS | PASS | PASS |
| 인연 | 3/3 | PASS | PASS | PASS |
| 의리 | 3/3 | PASS | PASS | PASS |
| 효 | 3/3 | PASS | PASS | PASS |
| 한 | 3/3 | PASS | PASS | PASS |
| 체면 | 3/3 | PASS | PASS | PASS |
| 배려 | 3/3 | PASS | PASS | PASS |
| 겸손 | 3/3 | PASS | PASS | PASS |
| 소신 | 3/3 | PASS | PASS | PASS |
| 낭만 | 3/3 | PASS | PASS | PASS |
| 충 | 3/3 | PASS | PASS | PASS |
| 권선징악 | 3/3 | PASS | PASS | PASS |
| 출세 | 3/3 | PASS | PASS | PASS |
| 궁합 | 3/3 | PASS | PASS | PASS |
| 억울하다 | 3/3 | PASS | PASS | PASS |
| 아쉽다 | 3/3 | PASS | PASS | PASS |
| 섭섭하다 | 3/3 | PASS | PASS | PASS |
| 민망하다 | 3/3 | PASS | PASS | PASS |
| 무안하다 | 3/3 | PASS | PASS | PASS |
| 답답하다 | 3/3 | PASS | PASS | PASS |
| 야속하다 | 3/3 | PASS | PASS | PASS |
| 그립다 | 3/3 | PASS | PASS | PASS |
| 애틋하다 | 2/3 | PASS | PASS | FAIL |
| 정겹다 | 3/3 | PASS | PASS | PASS |
| 괜히 | 3/3 | PASS | PASS | PASS |
| 챙기다 | 3/3 | PASS | PASS | PASS |
| 신경 쓰다 | 3/3 | PASS | PASS | PASS |
| 흥겹다 | 3/3 | PASS | PASS | PASS |
| 눈치 | 3/3 | PASS | PASS | PASS |

## 전체 케이스 상세

| # | 단어 | 유형 | 문장 | 기대(G/M) | 실제(G/M) | Target | 결과 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | 정 | 의미 오류 | 정은 새로 산 노트북의 색깔이다. | True/False | True/False | 정 | PASS |
| 2 | 정 | 문법 오류 | 나는 오래 산 동네에 정이 드는 순간을 쫒았다. | False/True | False/True | 정 | PASS |
| 3 | 정 | 문법+의미 오류 | 노트북 색깔을 쫒는 것이 정이다. | False/False | False/False | 정 | PASS |
| 4 | 서운하다 | 의미 오류 | 새로 산 책상의 길이가 서운하다. | True/False | True/False | 서운하다 | PASS |
| 5 | 서운하다 | 문법 오류 | 친구가 연락을 안 해서 서운한 마음으로 문자를 쫒았다. | False/True | False/True | 서운하다 | PASS |
| 6 | 서운하다 | 문법+의미 오류 | 책상 길이를 쫒는 감정이 서운하다. | False/False | False/False | 서운하다 | PASS |
| 7 | 인연 | 의미 오류 | 인연은 냉장고 온도를 낮추는 버튼이다. | True/False | True/False | 인연 | PASS |
| 8 | 인연 | 문법 오류 | 우연히 다시 만난 인연을 떠올리며 친구를 쫒았다. | False/True | False/True | 인연 | PASS |
| 9 | 인연 | 문법+의미 오류 | 냉장고 버튼을 쫒는 것이 인연이다. | False/False | False/False | 인연 | PASS |
| 10 | 의리 | 의미 오류 | 의리는 스마트폰 배터리 잔량이다. | True/False | True/False | 의리 | PASS |
| 11 | 의리 | 문법 오류 | 나는 의리를 지키는 친구를 쫒았다. | False/True | False/True | 의리 | PASS |
| 12 | 의리 | 문법+의미 오류 | 배터리 잔량을 쫒는 것이 의리이다. | False/False | False/False | 의리 | PASS |
| 13 | 효 | 의미 오류 | 효는 커피의 단맛을 재는 숫자이다. | True/False | True/False | 효 | PASS |
| 14 | 효 | 문법 오류 | 그는 효를 다하려고 부모님을 쫒아갔다. | False/True | False/True | 효 | PASS |
| 15 | 효 | 문법+의미 오류 | 커피 단맛을 쫒는 숫자가 효이다. | False/False | False/False | 효 | PASS |
| 16 | 한 | 의미 오류 | 한은 버스 번호를 세는 단위이다. | True/False | True/False | 한 | PASS |
| 17 | 한 | 문법 오류 | 그는 오래 품은 한을 풀 기회를 쫒았다. | False/True | False/True | 한 | PASS |
| 18 | 한 | 문법+의미 오류 | 버스 번호를 쫒는 단위가 한이다. | False/False | False/False | 한 | PASS |
| 19 | 체면 | 의미 오류 | 체면은 운동화 끈을 묶는 방법이다. | True/False | True/False | 체면 | PASS |
| 20 | 체면 | 문법 오류 | 여자친구 앞에서 체면을 세우려고 급히 공을 쫒았다. | False/True | False/True | 체면 | PASS |
| 21 | 체면 | 문법+의미 오류 | 운동화 끈 묶는 법을 쫒는 것이 체면이다. | False/False | False/False | 체면 | PASS |
| 22 | 배려 | 의미 오류 | 배려는 라면 물의 양이다. | True/False | True/False | 배려 | PASS |
| 23 | 배려 | 문법 오류 | 그는 친구를 배려하려고 늦은 버스를 쫒았다. | False/True | False/True | 배려 | PASS |
| 24 | 배려 | 문법+의미 오류 | 라면 물의 양을 쫒는 태도가 배려이다. | False/False | False/False | 배려 | PASS |
| 25 | 겸손 | 의미 오류 | 겸손은 컴퓨터 화면의 밝기이다. | True/False | True/False | 겸손 | PASS |
| 26 | 겸손 | 문법 오류 | 그는 겸손한 태도를 지키며 박수를 쫒았다. | False/True | False/True | 겸손 | PASS |
| 27 | 겸손 | 문법+의미 오류 | 화면 밝기를 쫒는 것이 겸손이다. | False/False | False/False | 겸손 | PASS |
| 28 | 소신 | 의미 오류 | 소신은 의자의 높이를 조절하는 손잡이다. | True/False | True/False | 소신 | PASS |
| 29 | 소신 | 문법 오류 | 그는 자기 소신을 지키며 유행을 쫒지 않았다. | False/True | False/True | 소신 | PASS |
| 30 | 소신 | 문법+의미 오류 | 의자 손잡이를 쫒는 생각이 소신이다. | False/False | False/False | 소신 | PASS |
| 31 | 낭만 | 의미 오류 | 낭만은 세탁기의 회전 속도이다. | True/False | True/False | 낭만 | PASS |
| 32 | 낭만 | 문법 오류 | 그는 비 오는 밤의 낭만을 쫒았다. | False/True | False/True | 낭만 | PASS |
| 33 | 낭만 | 문법+의미 오류 | 세탁기 회전 속도를 쫒는 것이 낭만이다. | False/False | False/False | 낭만 | PASS |
| 34 | 충 | 의미 오류 | 충은 휴대폰 충전기의 케이블 길이다. | True/False | True/False | 충 | PASS |
| 35 | 충 | 문법 오류 | 장군은 나라에 충을 다하려고 적을 쫒았다. | False/True | False/True | 충 | PASS |
| 36 | 충 | 문법+의미 오류 | 케이블 길이를 쫒는 마음이 충이다. | False/False | False/False | 충 | PASS |
| 37 | 권선징악 | 의미 오류 | 무조건 이익을 쫓는 것이 권선징악이다. | True/False | True/False | 권선징악 | PASS |
| 38 | 권선징악 | 문법 오류 | 고전 소설의 권선징악 결말을 쫒았다. | False/True | False/True | 권선징악 | PASS |
| 39 | 권선징악 | 문법+의미 오류 | 무조건 이익을 쫒는 것이 권선징악이다. | False/False | False/False | 권선징악 | PASS |
| 40 | 출세 | 의미 오류 | 출세는 냉장고 문을 여는 동작이다. | True/False | True/False | 출세 | PASS |
| 41 | 출세 | 문법 오류 | 그는 사회적으로 출세하려고 기회를 쫒았다. | False/True | False/True | 출세 | PASS |
| 42 | 출세 | 문법+의미 오류 | 냉장고 문을 쫒는 동작이 출세이다. | False/False | False/False | 출세 | PASS |
| 43 | 궁합 | 의미 오류 | 궁합은 신발의 무게를 뜻한다. | True/False | True/False | 궁합 | PASS |
| 44 | 궁합 | 문법 오류 | 이 두 음식의 궁합을 알아보려고 맛을 쫒았다. | False/True | False/True | 궁합 | PASS |
| 45 | 궁합 | 문법+의미 오류 | 신발 무게를 쫒는 것이 궁합이다. | False/False | False/False | 궁합 | PASS |
| 46 | 억울하다 | 의미 오류 | 컵의 색깔이 억울하다. | True/False | True/False | 억울하다 | PASS |
| 47 | 억울하다 | 문법 오류 | 하지 않은 일로 억울해서 진실을 쫒았다. | False/True | False/True | 억울하다 | PASS |
| 48 | 억울하다 | 문법+의미 오류 | 컵 색깔을 쫒는 기분이 억울하다. | False/False | False/False | 억울하다 | PASS |
| 49 | 아쉽다 | 의미 오류 | 형광등의 전압이 아쉽다. | True/False | True/False | 아쉽다 | PASS |
| 50 | 아쉽다 | 문법 오류 | 여행이 끝나 아쉬워서 떠나는 버스를 쫒았다. | False/True | False/True | 아쉽다 | PASS |
| 51 | 아쉽다 | 문법+의미 오류 | 형광등 전압을 쫒는 감정이 아쉽다. | False/False | False/False | 아쉽다 | PASS |
| 52 | 섭섭하다 | 의미 오류 | 책상의 네 번째 다리가 섭섭하다. | True/False | True/False | 섭섭하다 | PASS |
| 53 | 섭섭하다 | 문법 오류 | 인사도 못 해서 섭섭한 마음으로 친구를 쫒았다. | False/True | False/True | 섭섭하다 | PASS |
| 54 | 섭섭하다 | 문법+의미 오류 | 책상 다리를 쫒는 감정이 섭섭하다. | False/False | False/False | 섭섭하다 | PASS |
| 55 | 민망하다 | 의미 오류 | 지하철 노선 번호가 민망하다. | True/False | True/False | 민망하다 | PASS |
| 56 | 민망하다 | 문법 오류 | 실수해서 민망한 마음에 시선을 쫒았다. | False/True | False/True | 민망하다 | PASS |
| 57 | 민망하다 | 문법+의미 오류 | 노선 번호를 쫒는 기분이 민망하다. | False/False | False/False | 민망하다 | PASS |
| 58 | 무안하다 | 의미 오류 | 냄비 뚜껑의 지름이 무안하다. | True/False | True/False | 무안하다 | PASS |
| 59 | 무안하다 | 문법 오류 | 인사를 무시당해 무안해서 친구를 쫒았다. | False/True | False/True | 무안하다 | PASS |
| 60 | 무안하다 | 문법+의미 오류 | 냄비 지름을 쫒는 감정이 무안하다. | False/False | False/False | 무안하다 | PASS |
| 61 | 답답하다 | 의미 오류 | 물병의 색깔이 답답하다. | True/False | True/False | 답답하다 | PASS |
| 62 | 답답하다 | 문법 오류 | 일이 안 풀려 답답해서 해결책을 쫒았다. | False/True | False/True | 답답하다 | PASS |
| 63 | 답답하다 | 문법+의미 오류 | 물병 색깔을 쫒는 마음이 답답하다. | False/False | False/False | 답답하다 | PASS |
| 64 | 야속하다 | 의미 오류 | 우산 손잡이의 길이가 야속하다. | True/False | True/False | 야속하다 | PASS |
| 65 | 야속하다 | 문법 오류 | 내 마음을 몰라주는 친구가 야속해서 답을 쫒았다. | False/True | False/True | 야속하다 | PASS |
| 66 | 야속하다 | 문법+의미 오류 | 우산 손잡이 길이를 쫒는 감정이 야속하다. | False/False | False/False | 야속하다 | PASS |
| 67 | 그립다 | 의미 오류 | 프린터 잉크의 점도가 그립다. | True/False | True/False | 그립다 | PASS |
| 68 | 그립다 | 문법 오류 | 고향이 그리워서 옛 기억을 쫒았다. | False/True | False/True | 그립다 | PASS |
| 69 | 그립다 | 문법+의미 오류 | 잉크 점도를 쫒는 마음이 그립다. | False/False | False/False | 그립다 | PASS |
| 70 | 애틋하다 | 의미 오류 | 계산기의 숫자 버튼이 애틋하다. | True/False | True/False | 애틋하다 | PASS |
| 71 | 애틋하다 | 문법 오류 | 두 사람의 애틋한 사연을 쫒았다. | False/True | False/True | 애틋하다 | PASS |
| 72 | 애틋하다 | 문법+의미 오류 | 계산기 버튼을 쫒는 감정이 애틋하다. | False/False | False/True | 애틋하다 | FAIL |
| 73 | 정겹다 | 의미 오류 | 와이파이 비밀번호 길이가 정겹다. | True/False | True/False | 정겹다 | PASS |
| 74 | 정겹다 | 문법 오류 | 정겨운 골목 풍경을 쫒았다. | False/True | False/True | 정겹다 | PASS |
| 75 | 정겹다 | 문법+의미 오류 | 비밀번호 길이를 쫒는 느낌이 정겹다. | False/False | False/False | 정겹다 | PASS |
| 76 | 괜히 | 의미 오류 | 괜히는 책상의 재질을 뜻한다. | True/False | True/False | 괜히 | PASS |
| 77 | 괜히 | 문법 오류 | 괜히 미안한 마음에 친구를 쫒았다. | False/True | False/True | 괜히 | PASS |
| 78 | 괜히 | 문법+의미 오류 | 책상 재질을 쫒는 것이 괜히이다. | False/False | False/False | 괜히 | PASS |
| 79 | 챙기다 | 의미 오류 | 챙기다는 전등 스위치의 색깔이다. | True/False | True/False | 챙기다 | PASS |
| 80 | 챙기다 | 문법 오류 | 바빠도 끼니를 챙기려고 시간을 쫒았다. | False/True | False/True | 챙기다 | PASS |
| 81 | 챙기다 | 문법+의미 오류 | 전등 색깔을 쫒는 동작이 챙기다이다. | False/False | False/False | 챙기다 | PASS |
| 82 | 신경 쓰다 | 의미 오류 | 신경 쓰다는 생물 시간에 배우는 전선의 이름이다. | True/False | True/False | 신경 쓰다 | PASS |
| 83 | 신경 쓰다 | 문법 오류 | 그는 친구 일을 신경쓰며 소식을 쫒았다. | False/True | False/True | 신경 쓰다 | PASS |
| 84 | 신경 쓰다 | 문법+의미 오류 | 전선 이름을 쫒는 것이 신경쓰다이다. | False/False | False/False | 신경 쓰다 | PASS |
| 85 | 흥겹다 | 의미 오류 | 냉장고의 온도가 흥겹다. | True/False | True/False | 흥겹다 | PASS |
| 86 | 흥겹다 | 문법 오류 | 흥겨운 음악 소리를 쫒았다. | False/True | False/True | 흥겹다 | PASS |
| 87 | 흥겹다 | 문법+의미 오류 | 냉장고 온도를 쫒는 기분이 흥겹다. | False/False | False/False | 흥겹다 | PASS |
| 88 | 눈치 | 의미 오류 | 눈치는 노트북 화면 크기를 뜻한다. | True/False | True/False | 눈치 | PASS |
| 89 | 눈치 | 문법 오류 | 그는 눈치가 빨라서 분위기를 쫒았다. | False/True | False/True | 눈치 | PASS |
| 90 | 눈치 | 문법+의미 오류 | 화면 크기를 쫒는 능력이 눈치이다. | False/False | False/False | 눈치 | PASS |

## 실패 케이스 예시

### #72 애틋하다 / 문법+의미 오류

- 문장: 계산기 버튼을 쫒는 감정이 애틋하다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=애틋하다
- 문법 제안: 계산기 버튼을 쫓는 감정이 애틋하다.
- 의미 제안: None

