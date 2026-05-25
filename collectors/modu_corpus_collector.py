import json
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parent))
from common import ensure_dir, read_env_required


BASE_URL = "https://kli.korean.go.kr/restapi/v1/corpus/download"
ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_DIR / "output" / "modu" / "modu_download_info.json"


def parse_response(response: requests.Response) -> Any:
    """모두의 말뭉치 응답이 JSON이 아니어도 메시지를 보존한다."""
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def find_download_message(raw: Any) -> str:
    raw_text = json.dumps(raw, ensure_ascii=False) if not isinstance(raw, str) else raw
    return raw_text


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    api_key = read_env_required("MODU_CORPUS_API_KEY")

    params = {"keyVal": api_key}
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    raw = parse_response(response)

    # 이번 단계에서는 대용량 파일을 받지 않고 다운로드 안내 응답만 저장한다.
    record = {
        "source": "modu_corpus",
        "request_url": BASE_URL,
        "raw": raw,
    }
    ensure_dir(OUTPUT_PATH.parent)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(find_download_message(raw))


if __name__ == "__main__":
    main()
