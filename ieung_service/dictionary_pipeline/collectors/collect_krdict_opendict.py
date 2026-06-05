import sys
from pathlib import Path

import requests
import xmltodict
from dotenv import load_dotenv
from tqdm import tqdm

sys.path.append(str(Path(__file__).resolve().parent))
from common import append_jsonl, load_seed_words, read_env_required, safe_sleep


ROOT_DIR = Path(__file__).resolve().parents[2]
SEED_PATH = ROOT_DIR / "seed_cultural_words.csv"

KRDICT_BASE_URL = "https://krdict.korean.go.kr/api/search"
KRDICT_OUTPUT_PATH = ROOT_DIR / "output" / "krdict" / "krdict_raw_results.jsonl"
KRDICT_FAILED_PATH = ROOT_DIR / "output" / "krdict" / "krdict_failed.jsonl"

OPENDICT_BASE_URL = "https://opendict.korean.go.kr/api/search"
OPENDICT_OUTPUT_PATH = ROOT_DIR / "output" / "opendict" / "opendict_raw_results.jsonl"
OPENDICT_FAILED_PATH = ROOT_DIR / "output" / "opendict" / "opendict_failed.jsonl"


def parse_krdict_response(response: requests.Response) -> dict:
    try:
        return xmltodict.parse(response.text)
    except Exception:
        return {"text": response.text}


def parse_opendict_response(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def collect_krdict_one(seed: dict, api_key: str, timeout: int = 20) -> None:
    query = seed["word"]
    params = {"key": api_key, "q": query}

    try:
        response = requests.get(KRDICT_BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        raw = parse_krdict_response(response)
        append_jsonl(
            KRDICT_OUTPUT_PATH,
            {
                "source": "krdict",
                "query": query,
                "seed": seed,
                "raw": raw,
            },
        )
    except Exception as exc:
        append_jsonl(
            KRDICT_FAILED_PATH,
            {
                "source": "krdict",
                "query": query,
                "seed": seed,
                "error": repr(exc),
            },
        )


def collect_opendict_one(seed: dict, api_key: str, timeout: int = 20) -> None:
    query = seed["word"]
    params = {"key": api_key, "q": query, "req_type": "json"}

    try:
        response = requests.get(OPENDICT_BASE_URL, params=params, timeout=timeout)
        response.raise_for_status()
        raw = parse_opendict_response(response)
        append_jsonl(
            OPENDICT_OUTPUT_PATH,
            {
                "source": "opendict",
                "query": query,
                "seed": seed,
                "raw": raw,
            },
        )
    except Exception as exc:
        append_jsonl(
            OPENDICT_FAILED_PATH,
            {
                "source": "opendict",
                "query": query,
                "seed": seed,
                "error": repr(exc),
            },
        )


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")
    krdict_api_key = read_env_required("KRDIC_API_KEY")
    opendict_api_key = read_env_required("OPENDICT_API_KEY")
    seeds = load_seed_words(SEED_PATH)

    for seed in tqdm(seeds, desc="KRDICT + OPENDICT collecting"):
        collect_krdict_one(seed, krdict_api_key)
        safe_sleep(0.3)
        collect_opendict_one(seed, opendict_api_key)
        safe_sleep(0.3)


if __name__ == "__main__":
    main()
