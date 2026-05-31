# 이응 데이터 수집 및 로컬 RAG 파이프라인

“이응”은 외국인 한국어 학습자에게 `정`, `눈치`, `서운하다`, `인연`, `의리`, `효`, `한`, `낭만`, `소신`, `겸손`, `권선징악`, `출세`, `궁합` 같은 한국 문화어휘를 설명하고, 사용자의 한국어 문장을 더 자연스러운 표현으로 교정하기 위한 RAG 기반 실험 프로젝트입니다.

이 저장소는 공공 언어 데이터를 수집하고, 사전 원본 응답을 정규화한 뒤, 검증된 RAG 문서를 로컬 ChromaDB에 적재하여 검색과 피드백 생성을 테스트하는 Python 파이프라인을 담고 있습니다.

## 현재 범위

- 한국어기초사전 raw 데이터 수집
- 우리말샘 raw 데이터 수집
- seed 문화어휘 CSV 관리
- raw JSONL 정규화
- RAG 문서 생성
- RAG 문서 품질 검증
- ChromaDB 로컬 인덱스 구축
- Gemini 또는 OpenAI 기반 검색/피드백 테스트

KCISA와 모두의 말뭉치는 인증 대기 중이므로 collector 골격만 포함되어 있으며, 현재 정규화 및 RAG 입력에서는 제외됩니다.

## 폴더 구조

```text
ieung_data_collector/
  .env.example
  .gitignore
  requirements.txt
  seed_cultural_words.csv
  collectors/
    common.py
    krdict_collector.py
    opendict_collector.py
    kcisa_collector.py
    modu_corpus_collector.py
  normalizers/
    common.py
    normalize_krdict.py
    normalize_opendict.py
    build_rag_documents.py
  validators/
    validate_rag_documents.py
  rag/
    build_chroma_index.py
    embedding_utils.py
    search_rag.py
    generate_feedback.py
    test_rag_pipeline.py
  output/
    krdict/
    opendict/
    kcisa/
    modu/
    normalized/
    validation/
  chroma_db/
```

`output/`과 `chroma_db/`의 생성 산출물은 `.gitignore`로 제외됩니다. API 응답, 검증 결과, 로컬 벡터DB는 각자 환경에서 다시 생성하는 것을 전제로 합니다.

## 설치

```bash
cd ieung_data_collector
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
```

## 환경 변수

`.env.example`을 참고해 `.env` 파일을 직접 만듭니다. 실제 `.env`는 절대 커밋하지 않습니다.

```env
KRDIC_API_KEY=your_krdict_api_key_here
OPENDICT_API_KEY=your_opendict_api_key_here
KCISA_SERVICE_KEY=your_kcisa_service_key_here
MODU_CORPUS_API_KEY=your_modu_corpus_api_key_here

GEMINI_API_KEY=여기에_Gemini_API_KEY
IEUNG_EMBEDDING_PROVIDER=gemini
IEUNG_CHAT_PROVIDER=gemini
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_CHAT_MODEL=gemini-2.5-flash

CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION_NAME=ieung_rag
```

OpenAI를 사용할 수도 있습니다.

```env
OPENAI_API_KEY=여기에_OpenAI_API_KEY
IEUNG_EMBEDDING_PROVIDER=openai
IEUNG_CHAT_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4.1-mini
```

API 없이 로컬 검색 흐름만 확인하려면 해시 기반 임베딩을 사용할 수 있습니다. 검색 품질은 낮지만 ChromaDB 흐름 테스트에는 유용합니다.

```env
IEUNG_EMBEDDING_PROVIDER=local
```

임베딩 provider를 바꾼 뒤에는 기존 벡터 차원과 섞이지 않도록 Chroma collection을 reset하세요.

## 1. 데이터 수집

한국어기초사전:


```bash
python collectors/krdict_collector.py
```

우리말샘:

```bash
python collectors/opendict_collector.py
```

KCISA 테스트 수집:

```bash
python collectors/kcisa_collector.py
```

모두의 말뭉치 다운로드 정보 확인:

```bash
python collectors/modu_corpus_collector.py
```

KCISA는 첫 실행 시 기본 10페이지만 수집하도록 되어 있습니다. 응답 구조와 매칭 품질을 확인한 뒤 범위를 늘리는 것을 권장합니다.

## 2. 정규화 및 RAG 문서 생성

수집된 raw JSONL을 정규화합니다.

```bash
python normalizers/normalize_krdict.py
python normalizers/normalize_opendict.py
python normalizers/build_rag_documents.py
```

생성되는 주요 파일:

- `output/normalized/normalized_words.jsonl`
- `output/normalized/normalized_definitions.jsonl`
- `output/normalized/normalized_examples.jsonl`
- `output/normalized/normalized_expressions.jsonl`
- `output/normalized/rag_documents.jsonl`

`normalize_krdict.py`는 기본 실행 시 `output/normalized/`의 기존 산출물을 초기화하고 seed 단어를 다시 씁니다. append 모드가 필요하면 `--append` 옵션을 사용합니다.

## 3. RAG 문서 품질 검증

자동 검색 결과에서 만들어진 RAG 문서에는 파생어, 동음이의어, 품사 노이즈가 섞일 수 있습니다. ChromaDB에 넣기 전에 검증합니다.

```bash
python validators/validate_rag_documents.py
```

생성되는 파일:

- `output/validation/rag_validation_report.md`
- `output/validation/rag_validation_summary.json`
- `output/validation/rag_documents_accepted.jsonl`
- `output/validation/rag_documents_rejected.jsonl`
- `output/validation/rag_documents_review_needed.jsonl`

상태 의미:

- `accepted`: 자동 기준을 통과한 문서입니다. ChromaDB에는 우선 이 파일만 넣는 것을 권장합니다.
- `rejected`: 명백한 검색 노이즈 또는 문화어휘 의미와 맞지 않는 문서입니다.
- `review_needed`: 파생어 또는 확장 표현 가능성이 있어 사람이 검수해야 하는 문서입니다.

`review_needed`는 사람이 검수한 뒤 accepted/rejected로 다시 병합하는 흐름을 권장합니다. 특히 `정`, `한`, `효`, `충` 같은 한 글자 단어는 엄격 필터링을 유지합니다.

## 4. ChromaDB 인덱스 구축

검증된 accepted 문서만 인덱싱하는 것을 권장합니다.

```bash
python rag/build_chroma_index.py --input output/validation/rag_documents_accepted.jsonl --reset
```

정규화 직후 전체 RAG 문서를 실험용으로 넣고 싶다면 기본 입력을 사용할 수 있습니다.

```bash
python rag/build_chroma_index.py --reset
```

현재는 로컬 `chroma_db/`에 저장되는 ChromaDB 기반입니다. 서비스 배포 단계에서는 같은 JSONL 구조를 유지한 채 Supabase `pgvector` 같은 외부 벡터 저장소로 이전할 수 있습니다.

## 5. 검색 및 피드백 테스트

검색 테스트:

```bash
python rag/search_rag.py
```

검색과 피드백 생성을 한 번에 테스트:

```bash
python rag/generate_feedback.py
```

터미널에서 문장을 직접 입력하며 전체 파이프라인 테스트:

```bash
python rag/test_rag_pipeline.py
```

예시 입력:

```text
나는 이 카페를 정이 들었다.
```

## 보안 주의

- `.env`는 커밋하지 않습니다.
- API 키는 `.env.example`에 실제 값 없이 형식만 기록합니다.
- `output/`의 raw 응답과 ChromaDB 로컬 저장소는 기본적으로 git에서 제외됩니다.
- GitHub에 올리기 전 `git status`로 `.env`가 staging되지 않았는지 확인하세요.

## 다음 단계

- `review_needed` 수동 검수 및 accepted 병합
- KCISA 문화 맥락 문서 `doc_type=culture_context` 추가
- 모두의 말뭉치 구어 예문 `doc_type=spoken_example` 추가
- ChromaDB에서 Supabase `pgvector`로 이전 실험
- 실제 서비스 API 서버와 연결
