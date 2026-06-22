# 30개 문화어휘 기능 검정 리포트

- 생성 시각: 2026-06-22 17:28:59
- 검정 범위: 30개 단어 x 3개 오류 유형 = 90개 문장
- 실행 모드: 비용 안전 모드(LLM API 호출 비활성화, 사전 metadata 조회 + fallback/후처리 로직 검정)
- 판정 기준: target_word, grammar.correct, meaning.correct가 기대값과 모두 일치하면 PASS

## 요약

| 항목 | 결과 |
| --- | ---: |
| 전체 케이스 PASS | 32/90 (35.6%) |
| 타겟 단어 감지 PASS | 90/90 (100.0%) |
| 문법 판정 PASS | 90/90 (100.0%) |
| 의미 판정 PASS | 32/90 (35.6%) |

## 오류 유형별 결과

| 오류 유형 | PASS | Target | Grammar | Meaning |
| --- | ---: | ---: | ---: | ---: |
| 의미 오류 | 1/30 | 30/30 | 30/30 | 1/30 |
| 문법 오류 | 30/30 | 30/30 | 30/30 | 30/30 |
| 문법+의미 오류 | 1/30 | 30/30 | 30/30 | 1/30 |

## 주요 발견

- 타겟 단어 감지는 90/90로 확인되었습니다.
- 문법 오류 케이스는 공통 표기 오류 `쫒` -> `쫓`를 포함하도록 설계했으며, 현재 후처리 규칙에서 대부분 잡힙니다.
- 의미 오류 케이스는 비용 안전 모드 기준으로 대부분 놓쳤습니다. 현재 fallback 의미 검증은 일반 의미 오용을 폭넓게 판정하지 못하고, 명시 규칙이 있는 일부 케이스만 잡습니다.
- 실제 Gemini 호출을 켠 운영 환경에서는 의미 판정이 더 좋아질 수 있지만, 비용과 네트워크 호출이 발생하므로 이번 리포트에는 포함하지 않았습니다.

## 개선 권장사항

1. seed의 `brief_meaning`과 사용자 문장의 핵심 서술어를 비교하는 일반 의미 검증 레이어를 추가합니다.
2. `meaning.correct=true`를 fallback 기본값으로 두지 말고, 사전 근거가 있어도 문맥 적합성 판단이 불확실하면 `review_needed` 성격의 상태를 둘지 검토합니다.
3. 문법 검증은 현재 특정 표기 오류 중심이므로 조사 오류, 띄어쓰기, 활용 오류 규칙을 단어별로 확장합니다.
4. 운영 품질 검정은 별도 승인 후 Render `/feedback` 엔드포인트에 대해 live LLM 모드로 90개를 한 번 더 실행하는 것이 좋습니다.

## 단어별 PASS 요약

| 단어 | PASS | 의미 오류 | 문법 오류 | 문법+의미 오류 |
| --- | ---: | --- | --- | --- |
| 정 | 1/3 | FAIL | PASS | FAIL |
| 서운하다 | 1/3 | FAIL | PASS | FAIL |
| 인연 | 1/3 | FAIL | PASS | FAIL |
| 의리 | 1/3 | FAIL | PASS | FAIL |
| 효 | 1/3 | FAIL | PASS | FAIL |
| 한 | 1/3 | FAIL | PASS | FAIL |
| 체면 | 1/3 | FAIL | PASS | FAIL |
| 배려 | 1/3 | FAIL | PASS | FAIL |
| 겸손 | 1/3 | FAIL | PASS | FAIL |
| 소신 | 1/3 | FAIL | PASS | FAIL |
| 낭만 | 1/3 | FAIL | PASS | FAIL |
| 충 | 1/3 | FAIL | PASS | FAIL |
| 권선징악 | 3/3 | PASS | PASS | PASS |
| 출세 | 1/3 | FAIL | PASS | FAIL |
| 궁합 | 1/3 | FAIL | PASS | FAIL |
| 억울하다 | 1/3 | FAIL | PASS | FAIL |
| 아쉽다 | 1/3 | FAIL | PASS | FAIL |
| 섭섭하다 | 1/3 | FAIL | PASS | FAIL |
| 민망하다 | 1/3 | FAIL | PASS | FAIL |
| 무안하다 | 1/3 | FAIL | PASS | FAIL |
| 답답하다 | 1/3 | FAIL | PASS | FAIL |
| 야속하다 | 1/3 | FAIL | PASS | FAIL |
| 그립다 | 1/3 | FAIL | PASS | FAIL |
| 애틋하다 | 1/3 | FAIL | PASS | FAIL |
| 정겹다 | 1/3 | FAIL | PASS | FAIL |
| 괜히 | 1/3 | FAIL | PASS | FAIL |
| 챙기다 | 1/3 | FAIL | PASS | FAIL |
| 신경 쓰다 | 1/3 | FAIL | PASS | FAIL |
| 흥겹다 | 1/3 | FAIL | PASS | FAIL |
| 눈치 | 1/3 | FAIL | PASS | FAIL |

## 전체 케이스 상세

| # | 단어 | 유형 | 문장 | 기대(G/M) | 실제(G/M) | Target | 결과 |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | 정 | 의미 오류 | 정은 새로 산 노트북의 색깔이다. | True/False | True/True | 정 | FAIL |
| 2 | 정 | 문법 오류 | 나는 오래 산 동네에 정이 드는 순간을 쫒았다. | False/True | False/True | 정 | PASS |
| 3 | 정 | 문법+의미 오류 | 노트북 색깔을 쫒는 것이 정이다. | False/False | False/True | 정 | FAIL |
| 4 | 서운하다 | 의미 오류 | 새로 산 책상의 길이가 서운하다. | True/False | True/True | 서운하다 | FAIL |
| 5 | 서운하다 | 문법 오류 | 친구가 연락을 안 해서 서운한 마음으로 문자를 쫒았다. | False/True | False/True | 서운하다 | PASS |
| 6 | 서운하다 | 문법+의미 오류 | 책상 길이를 쫒는 감정이 서운하다. | False/False | False/True | 서운하다 | FAIL |
| 7 | 인연 | 의미 오류 | 인연은 냉장고 온도를 낮추는 버튼이다. | True/False | True/True | 인연 | FAIL |
| 8 | 인연 | 문법 오류 | 우연히 다시 만난 인연을 떠올리며 친구를 쫒았다. | False/True | False/True | 인연 | PASS |
| 9 | 인연 | 문법+의미 오류 | 냉장고 버튼을 쫒는 것이 인연이다. | False/False | False/True | 인연 | FAIL |
| 10 | 의리 | 의미 오류 | 의리는 스마트폰 배터리 잔량이다. | True/False | True/True | 의리 | FAIL |
| 11 | 의리 | 문법 오류 | 나는 의리를 지키는 친구를 쫒았다. | False/True | False/True | 의리 | PASS |
| 12 | 의리 | 문법+의미 오류 | 배터리 잔량을 쫒는 것이 의리이다. | False/False | False/True | 의리 | FAIL |
| 13 | 효 | 의미 오류 | 효는 커피의 단맛을 재는 숫자이다. | True/False | True/True | 효 | FAIL |
| 14 | 효 | 문법 오류 | 그는 효를 다하려고 부모님을 쫒아갔다. | False/True | False/True | 효 | PASS |
| 15 | 효 | 문법+의미 오류 | 커피 단맛을 쫒는 숫자가 효이다. | False/False | False/True | 효 | FAIL |
| 16 | 한 | 의미 오류 | 한은 버스 번호를 세는 단위이다. | True/False | True/True | 한 | FAIL |
| 17 | 한 | 문법 오류 | 그는 오래 품은 한을 풀 기회를 쫒았다. | False/True | False/True | 한 | PASS |
| 18 | 한 | 문법+의미 오류 | 버스 번호를 쫒는 단위가 한이다. | False/False | False/True | 한 | FAIL |
| 19 | 체면 | 의미 오류 | 체면은 운동화 끈을 묶는 방법이다. | True/False | True/True | 체면 | FAIL |
| 20 | 체면 | 문법 오류 | 여자친구 앞에서 체면을 세우려고 급히 공을 쫒았다. | False/True | False/True | 체면 | PASS |
| 21 | 체면 | 문법+의미 오류 | 운동화 끈 묶는 법을 쫒는 것이 체면이다. | False/False | False/True | 체면 | FAIL |
| 22 | 배려 | 의미 오류 | 배려는 라면 물의 양이다. | True/False | True/True | 배려 | FAIL |
| 23 | 배려 | 문법 오류 | 그는 친구를 배려하려고 늦은 버스를 쫒았다. | False/True | False/True | 배려 | PASS |
| 24 | 배려 | 문법+의미 오류 | 라면 물의 양을 쫒는 태도가 배려이다. | False/False | False/True | 배려 | FAIL |
| 25 | 겸손 | 의미 오류 | 겸손은 컴퓨터 화면의 밝기이다. | True/False | True/True | 겸손 | FAIL |
| 26 | 겸손 | 문법 오류 | 그는 겸손한 태도를 지키며 박수를 쫒았다. | False/True | False/True | 겸손 | PASS |
| 27 | 겸손 | 문법+의미 오류 | 화면 밝기를 쫒는 것이 겸손이다. | False/False | False/True | 겸손 | FAIL |
| 28 | 소신 | 의미 오류 | 소신은 의자의 높이를 조절하는 손잡이다. | True/False | True/True | 소신 | FAIL |
| 29 | 소신 | 문법 오류 | 그는 자기 소신을 지키며 유행을 쫒지 않았다. | False/True | False/True | 소신 | PASS |
| 30 | 소신 | 문법+의미 오류 | 의자 손잡이를 쫒는 생각이 소신이다. | False/False | False/True | 소신 | FAIL |
| 31 | 낭만 | 의미 오류 | 낭만은 세탁기의 회전 속도이다. | True/False | True/True | 낭만 | FAIL |
| 32 | 낭만 | 문법 오류 | 그는 비 오는 밤의 낭만을 쫒았다. | False/True | False/True | 낭만 | PASS |
| 33 | 낭만 | 문법+의미 오류 | 세탁기 회전 속도를 쫒는 것이 낭만이다. | False/False | False/True | 낭만 | FAIL |
| 34 | 충 | 의미 오류 | 충은 휴대폰 충전기의 케이블 길이다. | True/False | True/True | 충 | FAIL |
| 35 | 충 | 문법 오류 | 장군은 나라에 충을 다하려고 적을 쫒았다. | False/True | False/True | 충 | PASS |
| 36 | 충 | 문법+의미 오류 | 케이블 길이를 쫒는 마음이 충이다. | False/False | False/True | 충 | FAIL |
| 37 | 권선징악 | 의미 오류 | 무조건 이익을 쫓는 것이 권선징악이다. | True/False | True/False | 권선징악 | PASS |
| 38 | 권선징악 | 문법 오류 | 고전 소설의 권선징악 결말을 쫒았다. | False/True | False/True | 권선징악 | PASS |
| 39 | 권선징악 | 문법+의미 오류 | 무조건 이익을 쫒는 것이 권선징악이다. | False/False | False/False | 권선징악 | PASS |
| 40 | 출세 | 의미 오류 | 출세는 냉장고 문을 여는 동작이다. | True/False | True/True | 출세 | FAIL |
| 41 | 출세 | 문법 오류 | 그는 사회적으로 출세하려고 기회를 쫒았다. | False/True | False/True | 출세 | PASS |
| 42 | 출세 | 문법+의미 오류 | 냉장고 문을 쫒는 동작이 출세이다. | False/False | False/True | 출세 | FAIL |
| 43 | 궁합 | 의미 오류 | 궁합은 신발의 무게를 뜻한다. | True/False | True/True | 궁합 | FAIL |
| 44 | 궁합 | 문법 오류 | 이 두 음식의 궁합을 알아보려고 맛을 쫒았다. | False/True | False/True | 궁합 | PASS |
| 45 | 궁합 | 문법+의미 오류 | 신발 무게를 쫒는 것이 궁합이다. | False/False | False/True | 궁합 | FAIL |
| 46 | 억울하다 | 의미 오류 | 컵의 색깔이 억울하다. | True/False | True/True | 억울하다 | FAIL |
| 47 | 억울하다 | 문법 오류 | 하지 않은 일로 억울해서 진실을 쫒았다. | False/True | False/True | 억울하다 | PASS |
| 48 | 억울하다 | 문법+의미 오류 | 컵 색깔을 쫒는 기분이 억울하다. | False/False | False/True | 억울하다 | FAIL |
| 49 | 아쉽다 | 의미 오류 | 형광등의 전압이 아쉽다. | True/False | True/True | 아쉽다 | FAIL |
| 50 | 아쉽다 | 문법 오류 | 여행이 끝나 아쉬워서 떠나는 버스를 쫒았다. | False/True | False/True | 아쉽다 | PASS |
| 51 | 아쉽다 | 문법+의미 오류 | 형광등 전압을 쫒는 감정이 아쉽다. | False/False | False/True | 아쉽다 | FAIL |
| 52 | 섭섭하다 | 의미 오류 | 책상의 네 번째 다리가 섭섭하다. | True/False | True/True | 섭섭하다 | FAIL |
| 53 | 섭섭하다 | 문법 오류 | 인사도 못 해서 섭섭한 마음으로 친구를 쫒았다. | False/True | False/True | 섭섭하다 | PASS |
| 54 | 섭섭하다 | 문법+의미 오류 | 책상 다리를 쫒는 감정이 섭섭하다. | False/False | False/True | 섭섭하다 | FAIL |
| 55 | 민망하다 | 의미 오류 | 지하철 노선 번호가 민망하다. | True/False | True/True | 민망하다 | FAIL |
| 56 | 민망하다 | 문법 오류 | 실수해서 민망한 마음에 시선을 쫒았다. | False/True | False/True | 민망하다 | PASS |
| 57 | 민망하다 | 문법+의미 오류 | 노선 번호를 쫒는 기분이 민망하다. | False/False | False/True | 민망하다 | FAIL |
| 58 | 무안하다 | 의미 오류 | 냄비 뚜껑의 지름이 무안하다. | True/False | True/True | 무안하다 | FAIL |
| 59 | 무안하다 | 문법 오류 | 인사를 무시당해 무안해서 친구를 쫒았다. | False/True | False/True | 무안하다 | PASS |
| 60 | 무안하다 | 문법+의미 오류 | 냄비 지름을 쫒는 감정이 무안하다. | False/False | False/True | 무안하다 | FAIL |
| 61 | 답답하다 | 의미 오류 | 물병의 색깔이 답답하다. | True/False | True/True | 답답하다 | FAIL |
| 62 | 답답하다 | 문법 오류 | 일이 안 풀려 답답해서 해결책을 쫒았다. | False/True | False/True | 답답하다 | PASS |
| 63 | 답답하다 | 문법+의미 오류 | 물병 색깔을 쫒는 마음이 답답하다. | False/False | False/True | 답답하다 | FAIL |
| 64 | 야속하다 | 의미 오류 | 우산 손잡이의 길이가 야속하다. | True/False | True/True | 야속하다 | FAIL |
| 65 | 야속하다 | 문법 오류 | 내 마음을 몰라주는 친구가 야속해서 답을 쫒았다. | False/True | False/True | 야속하다 | PASS |
| 66 | 야속하다 | 문법+의미 오류 | 우산 손잡이 길이를 쫒는 감정이 야속하다. | False/False | False/True | 야속하다 | FAIL |
| 67 | 그립다 | 의미 오류 | 프린터 잉크의 점도가 그립다. | True/False | True/True | 그립다 | FAIL |
| 68 | 그립다 | 문법 오류 | 고향이 그리워서 옛 기억을 쫒았다. | False/True | False/True | 그립다 | PASS |
| 69 | 그립다 | 문법+의미 오류 | 잉크 점도를 쫒는 마음이 그립다. | False/False | False/True | 그립다 | FAIL |
| 70 | 애틋하다 | 의미 오류 | 계산기의 숫자 버튼이 애틋하다. | True/False | True/True | 애틋하다 | FAIL |
| 71 | 애틋하다 | 문법 오류 | 두 사람의 애틋한 사연을 쫒았다. | False/True | False/True | 애틋하다 | PASS |
| 72 | 애틋하다 | 문법+의미 오류 | 계산기 버튼을 쫒는 감정이 애틋하다. | False/False | False/True | 애틋하다 | FAIL |
| 73 | 정겹다 | 의미 오류 | 와이파이 비밀번호 길이가 정겹다. | True/False | True/True | 정겹다 | FAIL |
| 74 | 정겹다 | 문법 오류 | 정겨운 골목 풍경을 쫒았다. | False/True | False/True | 정겹다 | PASS |
| 75 | 정겹다 | 문법+의미 오류 | 비밀번호 길이를 쫒는 느낌이 정겹다. | False/False | False/True | 정겹다 | FAIL |
| 76 | 괜히 | 의미 오류 | 괜히는 책상의 재질을 뜻한다. | True/False | True/True | 괜히 | FAIL |
| 77 | 괜히 | 문법 오류 | 괜히 미안한 마음에 친구를 쫒았다. | False/True | False/True | 괜히 | PASS |
| 78 | 괜히 | 문법+의미 오류 | 책상 재질을 쫒는 것이 괜히이다. | False/False | False/True | 괜히 | FAIL |
| 79 | 챙기다 | 의미 오류 | 챙기다는 전등 스위치의 색깔이다. | True/False | True/True | 챙기다 | FAIL |
| 80 | 챙기다 | 문법 오류 | 바빠도 끼니를 챙기려고 시간을 쫒았다. | False/True | False/True | 챙기다 | PASS |
| 81 | 챙기다 | 문법+의미 오류 | 전등 색깔을 쫒는 동작이 챙기다이다. | False/False | False/True | 챙기다 | FAIL |
| 82 | 신경 쓰다 | 의미 오류 | 신경 쓰다는 생물 시간에 배우는 전선의 이름이다. | True/False | True/True | 신경 쓰다 | FAIL |
| 83 | 신경 쓰다 | 문법 오류 | 그는 친구 일을 신경쓰며 소식을 쫒았다. | False/True | False/True | 신경 쓰다 | PASS |
| 84 | 신경 쓰다 | 문법+의미 오류 | 전선 이름을 쫒는 것이 신경쓰다이다. | False/False | False/True | 신경 쓰다 | FAIL |
| 85 | 흥겹다 | 의미 오류 | 냉장고의 온도가 흥겹다. | True/False | True/True | 흥겹다 | FAIL |
| 86 | 흥겹다 | 문법 오류 | 흥겨운 음악 소리를 쫒았다. | False/True | False/True | 흥겹다 | PASS |
| 87 | 흥겹다 | 문법+의미 오류 | 냉장고 온도를 쫒는 기분이 흥겹다. | False/False | False/True | 흥겹다 | FAIL |
| 88 | 눈치 | 의미 오류 | 눈치는 노트북 화면 크기를 뜻한다. | True/False | True/True | 눈치 | FAIL |
| 89 | 눈치 | 문법 오류 | 그는 눈치가 빨라서 분위기를 쫒았다. | False/True | False/True | 눈치 | PASS |
| 90 | 눈치 | 문법+의미 오류 | 화면 크기를 쫒는 능력이 눈치이다. | False/False | False/True | 눈치 | FAIL |

## 실패 케이스 예시

### #1 정 / 의미 오류

- 문장: 정은 새로 산 노트북의 색깔이다.
- 기대: grammar=True, meaning=False
- 실제: grammar=True, meaning=True, target=정
- 문법 제안: None
- 의미 제안: None

### #3 정 / 문법+의미 오류

- 문장: 노트북 색깔을 쫒는 것이 정이다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=정
- 문법 제안: 노트북 색깔을 쫓는 것이 정이다.
- 의미 제안: None

### #4 서운하다 / 의미 오류

- 문장: 새로 산 책상의 길이가 서운하다.
- 기대: grammar=True, meaning=False
- 실제: grammar=True, meaning=True, target=서운하다
- 문법 제안: None
- 의미 제안: None

### #6 서운하다 / 문법+의미 오류

- 문장: 책상 길이를 쫒는 감정이 서운하다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=서운하다
- 문법 제안: 책상 길이를 쫓는 감정이 서운하다.
- 의미 제안: None

### #7 인연 / 의미 오류

- 문장: 인연은 냉장고 온도를 낮추는 버튼이다.
- 기대: grammar=True, meaning=False
- 실제: grammar=True, meaning=True, target=인연
- 문법 제안: None
- 의미 제안: None

### #9 인연 / 문법+의미 오류

- 문장: 냉장고 버튼을 쫒는 것이 인연이다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=인연
- 문법 제안: 냉장고 버튼을 쫓는 것이 인연이다.
- 의미 제안: None

### #10 의리 / 의미 오류

- 문장: 의리는 스마트폰 배터리 잔량이다.
- 기대: grammar=True, meaning=False
- 실제: grammar=True, meaning=True, target=의리
- 문법 제안: None
- 의미 제안: None

### #12 의리 / 문법+의미 오류

- 문장: 배터리 잔량을 쫒는 것이 의리이다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=의리
- 문법 제안: 배터리 잔량을 쫓는 것이 의리이다.
- 의미 제안: None

### #13 효 / 의미 오류

- 문장: 효는 커피의 단맛을 재는 숫자이다.
- 기대: grammar=True, meaning=False
- 실제: grammar=True, meaning=True, target=효
- 문법 제안: None
- 의미 제안: None

### #15 효 / 문법+의미 오류

- 문장: 커피 단맛을 쫒는 숫자가 효이다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=효
- 문법 제안: 커피 단맛을 쫓는 숫자가 효이다.
- 의미 제안: None

### #16 한 / 의미 오류

- 문장: 한은 버스 번호를 세는 단위이다.
- 기대: grammar=True, meaning=False
- 실제: grammar=True, meaning=True, target=한
- 문법 제안: None
- 의미 제안: None

### #18 한 / 문법+의미 오류

- 문장: 버스 번호를 쫒는 단위가 한이다.
- 기대: grammar=False, meaning=False
- 실제: grammar=False, meaning=True, target=한
- 문법 제안: 버스 번호를 쫓는 단위가 한이다.
- 의미 제안: None

