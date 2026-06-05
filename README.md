# RAG_LLM

현재 실행에 필요한 전과정은 [ieung_service](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service) 폴더 안에 모아두었습니다.

이 폴더 안에는 아래가 함께 들어 있습니다.

- 사전 수집/정규화/검증/임베딩
- 모두의 말뭉치 정제/라벨링/검색 인덱스
- 최종 피드백 생성
- Flask 마이크로서버
- `output`, `raw_data`, `chroma_db`
- 설정 파일과 seed 파일

## 핵심 폴더

- [ieung_service](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service)
- [dictionary_pipeline](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\dictionary_pipeline)
- [spoken_labeling](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\spoken_labeling)
- [api_server](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\api_server)

## 직접 수정하는 파일

- [seed_cultural_words.csv](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\seed_cultural_words.csv)
- [spoken_search_config.json](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\spoken_search_config.json)
- [tpo_config.json](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\tpo_config.json)
- [generate_feedback.py](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\generate_feedback.py)
- [feedback_pipeline.py](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\feedback_pipeline.py)
- [server.py](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\ieung_service\server.py)

## 서버 엔드포인트

- `GET /health`
- `GET /config`
- `POST /feedback`
- `POST /feedback/debug`

## 실행 예시

패키지 설치:

```bash
pip install -r requirements.txt
```

Flask 서버 실행:

```bash
python ieung_service/server.py
```

자세한 실행 순서는 [RUN_ORDER.md](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\RUN_ORDER.md)를 보면 됩니다.
