import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parent))
from common import append_jsonl, load_seed_words, read_env_required, safe_sleep


BASE_URL = "https://opendict.korean.go.kr/api/search"
ROOT_DIR = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"
OUTPUT_PATH = ROOT_DIR / "output" / "opendict" / "opendict_raw_results.jsonl"
FAILED_PATH = ROOT_DIR / "output" / "opendict" / "opendict_failed.jsonl"


def parse_response(response: requests.Response) -> dict:
    """우리말샘은 req_type=json을 요청하지만 예외 상황을 대비해 텍스트도 보존한다."""
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def collect_one(seed: dict, api_key: str, timeout: int = 20) -> None:
    query = seed["word"]
    params = {"key": api_key, "q": query, "req_type": "json"}

    try:
        response = requests.get(BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        raw = parse_response(response)

        append_jsonl(
            OUTPUT_PATH,
            {
                "source": "opendict",
                "query": query,
                "seed": seed,
                "raw": raw,
            },
        )
    except Exception as exc:
        append_jsonl(
            FAILED_PATH,
            {
                "source": "opendict",
                "query": query,
                "seed": seed,
                "error": repr(exc),
            },
        )


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    api_key = read_env_required("OPENDICT_API_KEY")
    seeds = load_seed_words(SEED_PATH)

    for seed in tqdm(seeds, desc="OPENDICT collecting"):
        collect_one(seed, api_key)
        safe_sleep(0.3)


if __name__ == "__main__":
    main()
