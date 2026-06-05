# 실행 순서 가이드

현재 전과정은 [ieung_service](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service) 폴더 안에서 관리합니다.

## 1. 패키지 설치

```bash
pip install -r requirements.txt
```

## 2. 환경 변수 확인

- [ieung_service\.env](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\.env)
- 예시 파일: [ieung_service\.env.example](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\.env.example)

## 3. 사전 수집

```bash
python ieung_service/dictionary_pipeline/collectors/collect_krdict_opendict.py
```

## 4. 사전 정규화

```bash
python ieung_service/dictionary_pipeline/normalizers/normalize_krdict.py
python ieung_service/dictionary_pipeline/normalizers/normalize_opendict.py
python ieung_service/dictionary_pipeline/normalizers/build_rag_documents.py
```

## 5. 사전 검증

```bash
python ieung_service/dictionary_pipeline/validators/validate_rag_documents.py
```

## 6. 사전 인덱싱

```bash
python ieung_service/dictionary_pipeline/retrieval/build_chroma_index.py --input ieung_service/output/validation/rag_documents_accepted.jsonl --reset
```

## 7. 모두의 말뭉치 정제

```bash
python ieung_service/spoken_labeling/build_spoken_reference_dataset.py
```

## 8. 말뭉치 검색 인덱스 생성

```bash
python ieung_service/spoken_labeling/build_spoken_lookup_index.py
```

## 9. 피드백 로컬 테스트

```bash
python ieung_service/feedback_pipeline.py
```

## 10. Flask 마이크로서버 실행

```bash
python ieung_service/server.py
```

## 주요 API

- `GET http://127.0.0.1:5000/health`
- `GET http://127.0.0.1:5000/config`
- `POST http://127.0.0.1:5000/feedback`
- `POST http://127.0.0.1:5000/feedback/debug`
