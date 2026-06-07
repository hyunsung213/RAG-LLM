# Render 배포 가이드

현재 폴더는 운영 배포만을 위해 최소 런타임 자산만 모아둔 Render 전용 폴더입니다.

포함된 것:
- Flask 서버 코드
- 사전 검색 코드
- 구어체 검색 코드
- `chroma_db`
- `spoken_lookup_index.json`
- `rag_documents_accepted.jsonl`
- Dockerfile
- Gunicorn 진입점

포함하지 않은 것:
- `raw_data`
- 대용량 정제 원본 JSONL
- 수집/정규화/검증 전체 파이프라인

## 1. 배포 전 준비

이 폴더를 별도 Git 저장소로 올리거나, 현재 저장소를 그대로 사용할 경우 Render에서 Root Directory를 `render_deploy`로 지정합니다.

더 빠른 방식:
- 저장소 루트의 [render.yaml](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\render.yaml)을 사용해 Blueprint로 생성
- 이 경우 Render가 `rootDir: render_deploy` 설정을 읽습니다.

필수 환경변수:
- `GEMINI_API_KEY`

선택 환경변수:
- `OPENAI_API_KEY`
- `IEUNG_CHAT_PROVIDER`
- `IEUNG_EMBEDDING_PROVIDER`
- `GEMINI_CHAT_MODEL`
- `GEMINI_EMBEDDING_MODEL`

현재 기본값은 `.env`에 반영되어 있습니다.

빠르게 확인하려면 [ENV_CHECKLIST.md](C:\Users\SHIN HYUN SEONG\Desktop\RAG_LLM\render_deploy\ENV_CHECKLIST.md)를 보면 됩니다.

## 2. Render에서 Web Service 생성

1. Render 대시보드에서 `New +` -> `Blueprint` 또는 `Web Service`
2. GitHub 저장소 연결
3. 배포할 저장소 선택
4. `render.yaml`을 사용할 경우 Blueprint 미리보기에서 서비스 설정 확인
5. 수동 생성이라면 서비스 생성 화면에서 아래처럼 설정

- Runtime: `Docker`
- Root Directory: `render_deploy`
- Region: 한국 사용자 기준 가까운 리전 우선
- Instance Type: 시작은 `Starter` 권장

## 3. 환경변수 입력

Render 대시보드의 `Environment`에서 아래를 설정합니다.

필수:
- `GEMINI_API_KEY`

권장:
- `IEUNG_CHAT_PROVIDER=gemini`
- `IEUNG_EMBEDDING_PROVIDER=gemini`
- `GEMINI_CHAT_MODEL=gemini-2.5-flash`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`
- `CHROMA_PERSIST_DIR=./chroma_db`
- `CHROMA_COLLECTION_NAME=ieung_rag`

주의:
- `.env` 파일은 헬스체크용 기본값/로컬 호환용입니다.
- 실제 비밀키는 Render Dashboard 환경변수에 넣는 방식으로 운영합니다.

## 4. 배포 후 확인

배포 완료 후 아래 경로로 확인합니다.

- `GET /health`
- `GET /config`

예시:

```bash
curl https://<your-render-domain>/health
```

정상이라면 `status: ok` 또는 최소한 필요한 파일 상태가 `true`로 보입니다.

## 5. 실제 API 테스트

```bash
curl -X POST https://<your-render-domain>/feedback \
  -H "Content-Type: application/json" \
  -d '{"sentence":"나는 이 카페를 정이 들었다."}'
```

디버그:

```bash
curl -X POST https://<your-render-domain>/feedback/debug \
  -H "Content-Type: application/json" \
  -d '{"sentence":"저는 이 카페에 정이 많이 들었습니다."}'
```

## 6. 추천 운영 방식

- 백엔드와 같은 클라우드 프로젝트 안에 두되, 별도 서비스로 운영
- 백엔드는 이 Flask 서비스의 `/feedback`만 내부 호출
- 외부 공개는 백엔드 또는 API Gateway만 담당

## 7. 현재 폴더 기준 Start 동작

Render는 `Dockerfile`을 사용합니다.

컨테이너 시작 명령:

```bash
gunicorn wsgi:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 2 --timeout 120
```

## 8. 폴더 갱신

원본 `ieung_service`에 변경이 생기면, 이 폴더도 다시 동기화해야 합니다.

동기화 대상 핵심 파일:
- `generate_feedback.py`
- `api_server/`
- `spoken_labeling/search_spoken_examples.py`
- `dictionary_pipeline/retrieval/`
- `spoken_search_config.json`
- `tpo_config.json`
- `output/normalized/spoken_lookup_index.json`
- `output/validation/rag_documents_accepted.jsonl`
- `chroma_db/`
