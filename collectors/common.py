import csv
import json
import os
import time
from pathlib import Path


def ensure_dir(path: Path) -> None:
    """저장 대상 디렉터리가 없으면 생성한다."""
    Path(path).mkdir(parents=True, exist_ok=True)


def load_seed_words(csv_path: Path) -> list[dict]:
    """문화어휘 seed CSV를 한 줄씩 읽어 dict 목록으로 반환한다."""
    with Path(csv_path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_jsonl(path: Path, data: dict) -> None:
    """대용량 수집을 고려해 JSONL 파일에 한 건씩 append 저장한다."""
    path = Path(path)
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def safe_sleep(seconds: float) -> None:
    """API 서버에 부담을 주지 않기 위한 요청 간 대기."""
    if seconds > 0:
        time.sleep(seconds)


def read_env_required(name: str) -> str:
    """필수 환경변수가 없으면 명확한 메시지로 중단한다."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"필수 환경변수 {name}이 설정되어 있지 않습니다. .env 파일을 확인하세요.")
    return value
