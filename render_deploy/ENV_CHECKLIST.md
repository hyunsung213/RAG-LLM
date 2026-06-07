# Render 환경변수 체크리스트

## 필수

- `GEMINI_API_KEY`

## 선택

- `OPENAI_API_KEY`

## 기본 운영값

- `IEUNG_CHAT_PROVIDER=gemini`
- `IEUNG_EMBEDDING_PROVIDER=gemini`
- `GEMINI_CHAT_MODEL=gemini-2.5-flash`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`
- `CHROMA_PERSIST_DIR=./chroma_db`
- `CHROMA_COLLECTION_NAME=ieung_rag`
- `IEUNG_API_HOST=0.0.0.0`
- `IEUNG_API_PORT=10000`

## Render 대시보드 입력 순서

1. `GEMINI_API_KEY` 입력
2. `OPENAI_API_KEY`는 필요할 때만 입력
3. 나머지 기본 운영값은 `render.yaml`에 이미 들어 있으므로, 보통 별도 입력이 필요 없음

## 배포 후 확인

- `GET /health`
- `GET /config`
- `POST /feedback`

## 메모

- 현재 배포본은 `render_deploy` 폴더를 기준으로 동작합니다.
- 실제 비밀키는 `.env`가 아니라 Render Dashboard 환경변수에 넣는 방식으로 운영하는 것을 권장합니다.
