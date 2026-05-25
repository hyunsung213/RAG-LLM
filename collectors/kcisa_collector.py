import json
import sys
from pathlib import Path
from typing import Any

import requests
import xmltodict
from dotenv import load_dotenv
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parent))
from common import append_jsonl, load_seed_words, read_env_required, safe_sleep


BASE_URL = "http://api.kcisa.kr/openapi/API_SOP_027/request"
ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"
RAW_PAGES_PATH = ROOT_DIR / "output" / "kcisa" / "kcisa_raw_pages.jsonl"
MATCHED_ITEMS_PATH = ROOT_DIR / "output" / "kcisa" / "kcisa_matched_items.jsonl"
FAILED_PATH = ROOT_DIR / "output" / "kcisa" / "kcisa_failed.jsonl"


def parse_response(response: requests.Response) -> Any:
    """KCISA 응답 형식이 JSON/XML/텍스트 중 무엇이든 원본 의미를 최대한 보존한다."""
    try:
        return response.json()
    except ValueError:
        pass

    try:
        return xmltodict.parse(response.text)
    except Exception:
        return {"text": response.text}


def as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_items(raw: Any) -> list[dict]:
    """공공 API 응답 구조 변동에 대비해 여러 가능한 item 경로를 처리한다."""
    candidates = []

    if isinstance(raw, dict):
        candidates.extend(
            [
                raw.get("response", {}).get("body", {}).get("items", {}).get("item"),
                raw.get("response", {}).get("body", {}).get("items"),
                raw.get("body", {}).get("items", {}).get("item"),
                raw.get("items", {}).get("item"),
                raw.get("item"),
                raw.get("data"),
                raw.get("list"),
            ]
        )

    items: list[dict] = []
    for candidate in candidates:
        for item in as_list(candidate):
            if isinstance(item, dict):
                items.append(item)

    if items:
        return items

    # 알려진 경로가 없을 때는 item 키를 재귀적으로 탐색한다.
    return find_items_recursively(raw)


def find_items_recursively(value: Any) -> list[dict]:
    found: list[dict] = []

    if isinstance(value, dict):
        for key, child in value.items():
            if key == "item":
                found.extend([item for item in as_list(child) if isinstance(item, dict)])
            else:
                found.extend(find_items_recursively(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(find_items_recursively(child))

    return found


def find_matched_seeds(item: dict, seeds: list[dict]) -> list[dict]:
    item_text = json.dumps(item, ensure_ascii=False)
    return [seed for seed in seeds if seed["word"] in item_text]


def collect_pages(
    api_key: str,
    seeds: list[dict],
    start_page: int = 1,
    end_page: int = 10,
    num_of_rows: int = 100,
    timeout: int = 30,
) -> None:
    for page_no in tqdm(range(start_page, end_page + 1), desc="KCISA collecting"):
        params = {"serviceKey": api_key, "numOfRows": num_of_rows, "pageNo": page_no}

        try:
            response = requests.get(BASE_URL, params=params, timeout=timeout)
            response.raise_for_status()
            raw = parse_response(response)

            append_jsonl(
                RAW_PAGES_PATH,
                {
                    "source": "kcisa_api_sop_027",
                    "pageNo": page_no,
                    "numOfRows": num_of_rows,
                    "raw": raw,
                },
            )

            for item in extract_items(raw):
                matched_seeds = find_matched_seeds(item, seeds)
                if matched_seeds:
                    append_jsonl(
                        MATCHED_ITEMS_PATH,
                        {
                            "source": "kcisa_api_sop_027",
                            "pageNo": page_no,
                            "matched_words": [seed["word"] for seed in matched_seeds],
                            "matched_seeds": matched_seeds,
                            "item": item,
                        },
                    )
        except Exception as exc:
            append_jsonl(
                FAILED_PATH,
                {
                    "source": "kcisa_api_sop_027",
                    "pageNo": page_no,
                    "numOfRows": num_of_rows,
                    "error": repr(exc),
                },
            )

        safe_sleep(0.5)


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    api_key = read_env_required("KCISA_SERVICE_KEY")
    seeds = load_seed_words(SEED_PATH)

    # 첫 실행은 1~10페이지 테스트 수집을 기본값으로 둔다.
    collect_pages(api_key=api_key, seeds=seeds, start_page=1, end_page=10, num_of_rows=100)


if __name__ == "__main__":
    main()
