import sys
from pathlib import Path

import requests
import xmltodict
from dotenv import load_dotenv
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parent))
from common import append_jsonl, load_seed_words, read_env_required, safe_sleep


BASE_URL = "https://krdict.korean.go.kr/api/search"
ROOT_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"
OUTPUT_PATH = ROOT_DIR / "output" / "krdict" / "krdict_raw_results.jsonl"
FAILED_PATH = ROOT_DIR / "output" / "krdict" / "krdict_failed.jsonl"


def parse_response(response: requests.Response) -> dict:
    """한국어기초사전은 XML 응답 가능성이 높으므로 XML 파싱을 우선한다."""
    try:
        return xmltodict.parse(response.text)
    except Exception:
        return {"text": response.text}


def collect_one(seed: dict, api_key: str, timeout: int = 20) -> None:
    query = seed["word"]
    params = {"key": api_key, "q": query}

    try:
        response = requests.get(BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        raw = parse_response(response)

        append_jsonl(
            OUTPUT_PATH,
            {
                "source": "krdict",
                "query": query,
                "seed": seed,
                "raw": raw,
            },
        )
    except Exception as exc:
        # 개별 요청 실패는 failed.jsonl에 남기고 다음 단어 수집을 계속한다.
        append_jsonl(
            FAILED_PATH,
            {
                "source": "krdict",
                "query": query,
                "seed": seed,
                "error": repr(exc),
            },
        )


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    api_key = read_env_required("KRDIC_API_KEY")
    seeds = load_seed_words(SEED_PATH)

    for seed in tqdm(seeds, desc="KRDIC collecting"):
        collect_one(seed, api_key)
        safe_sleep(0.3)


if __name__ == "__main__":
    main()
