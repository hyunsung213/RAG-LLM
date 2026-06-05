from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, request

from generate_feedback import collect_evidence, generate_feedback


SERVICE_DIR = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def json_error(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def service_status() -> dict:
    chroma_dir = SERVICE_DIR / "chroma_db"
    output_dir = SERVICE_DIR / "output"
    normalized_dir = output_dir / "normalized"
    validation_dir = output_dir / "validation"

    return {
        "service_dir": str(SERVICE_DIR),
        "env_ready": (SERVICE_DIR / ".env").exists(),
        "chroma_ready": chroma_dir.exists(),
        "spoken_index_ready": (normalized_dir / "spoken_lookup_index.json").exists(),
        "spoken_dataset_ready": (normalized_dir / "spoken_reference_dataset.jsonl").exists(),
        "dictionary_validation_ready": (validation_dir / "rag_documents_accepted.jsonl").exists(),
        "tpo_config_ready": (SERVICE_DIR / "tpo_config.json").exists(),
        "spoken_config_ready": (SERVICE_DIR / "spoken_search_config.json").exists(),
    }


def parse_sentence_payload() -> tuple[str | None, tuple | None]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, json_error("INVALID_JSON", "JSON 본문이 필요합니다.", 400)

    sentence = str(payload.get("sentence", "")).strip()
    if not sentence:
        return None, json_error("MISSING_SENTENCE", "`sentence` 값을 입력하세요.", 400)

    return sentence, None


def build_config_summary() -> dict:
    spoken_config = load_json(SERVICE_DIR / "spoken_search_config.json")
    tpo_config = load_json(SERVICE_DIR / "tpo_config.json")
    return {
        "target_words": spoken_config.get("target_words", []),
        "candidate_limits": spoken_config.get("candidate_limits", {}),
        "length_rules": spoken_config.get("length_rules", {}),
        "score_rules": spoken_config.get("score_rules", {}),
        "tpo_categories": {
            key: {
                "label": value.get("label", ""),
                "principle": value.get("principle", ""),
            }
            for key, value in tpo_config.items()
        },
    }


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

    @app.get("/health")
    def health():
        status = service_status()
        ready = all(
            [
                status["env_ready"],
                status["chroma_ready"],
                status["spoken_index_ready"],
                status["dictionary_validation_ready"],
                status["tpo_config_ready"],
                status["spoken_config_ready"],
            ]
        )
        return jsonify({"status": "ok" if ready else "degraded", **status}), (200 if ready else 503)

    @app.get("/config")
    def config_summary():
        try:
            return jsonify(build_config_summary())
        except Exception as exc:
            return json_error("CONFIG_LOAD_FAILED", str(exc), 500)

    @app.post("/feedback")
    def feedback():
        sentence, error = parse_sentence_payload()
        if error:
            return error

        try:
            result = generate_feedback(sentence)
            return jsonify(result)
        except Exception as exc:
            return json_error("FEEDBACK_FAILED", str(exc), 500)

    @app.post("/feedback/debug")
    def feedback_debug():
        sentence, error = parse_sentence_payload()
        if error:
            return error

        try:
            evidence = collect_evidence(sentence)
            result = generate_feedback(sentence)
            debug_payload = {
                "sentence": sentence,
                "target_word": evidence.get("target_word"),
                "dictionary_docs": evidence.get("dictionary_docs", []),
                "spoken_examples": evidence.get("spoken_result", {}).get("examples", []),
                "feedback": result,
            }
            return jsonify(debug_payload)
        except Exception as exc:
            return json_error("DEBUG_FEEDBACK_FAILED", str(exc), 500)

    @app.errorhandler(404)
    def not_found(_exc):
        return json_error("NOT_FOUND", "요청한 경로를 찾을 수 없습니다.", 404)

    @app.errorhandler(405)
    def method_not_allowed(_exc):
        return json_error("METHOD_NOT_ALLOWED", "허용되지 않은 메서드입니다.", 405)

    return app

