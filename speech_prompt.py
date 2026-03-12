import json
import re
from typing import Any, Dict, List

from llm_provider import llm_simple
from structured_schemas import SPEECH_PROMPT_NORMALIZATION_SCHEMA


_FILLER_PATTERN = re.compile(
    r"(?i)\b(?:hum+|uhm+|ahn+|hã+|ah+|eh+|mmm+)\b"
)
_MULTI_PUNCT_PATTERN = re.compile(r"([,.;:!?])(?:\s*\1)+")
_MULTI_SPACE_PATTERN = re.compile(r"\s+")


def clean_spoken_transcript(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = value.replace("\r", " ").replace("\n", " ")
    value = _FILLER_PATTERN.sub(" ", value)
    value = _MULTI_PUNCT_PATTERN.sub(r"\1", value)
    value = _MULTI_SPACE_PATTERN.sub(" ", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return value.strip(" \t,;")


def _guess_mode(transcript: str, requested_mode: str) -> str:
    wanted = str(requested_mode or "").strip().lower()
    if wanted in {"general", "userstory"}:
        return wanted
    normalized = str(transcript or "").lower()
    if any(term in normalized for term in ("user story", "userstory", "critério de aceitação", "aceitação", "epic", "feature")):
        return "userstory"
    return "general"


def _fallback_response(cleaned: str, requested_mode: str) -> Dict[str, Any]:
    notes: List[str] = []
    if cleaned:
        notes.append("Foi usada uma normalização conservadora porque a interpretação avançada não ficou disponível.")
    return {
        "raw_transcript": cleaned,
        "normalized_prompt": cleaned or "Ajuda-me com este pedido.",
        "confidence": "medium" if cleaned else "low",
        "inferred_mode": _guess_mode(cleaned, requested_mode),
        "notes": notes,
    }


def _parse_json_payload(raw: str) -> Dict[str, Any]:
    content = str(raw or "").strip()
    if not content:
        raise ValueError("empty_response")
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        parsed = json.loads(content[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("invalid_json")


async def normalize_spoken_prompt(
    transcript: str,
    mode: str = "general",
    language: str = "pt-PT",
) -> Dict[str, Any]:
    cleaned = clean_spoken_transcript(transcript)
    if not cleaned:
        return {
            "raw_transcript": "",
            "normalized_prompt": "",
            "confidence": "low",
            "inferred_mode": _guess_mode("", mode),
            "notes": ["Não foi possível recolher texto suficiente a partir da fala."],
        }

    requested_mode = _guess_mode(cleaned, mode)
    prompt = f"""
Transforma a transcrição de fala espontânea de um colega num prompt claro e útil para um assistente interno.

Contexto:
- idioma: {language or 'pt-PT'}
- modo ativo da aplicação: {requested_mode}

Regras obrigatórias:
- Remove hesitações, repetições, começos falsos e frases partidas.
- Mantém nomes de sistemas, ficheiros, equipas, áreas, produtos e termos funcionais exatamente como aparecem.
- Não inventes requisitos, números, datas ou contexto que não estejam na transcrição.
- Se houver ambiguidade relevante, mantém o pedido útil mas regista essa ambiguidade em "notes".
- O campo "normalized_prompt" deve ficar pronto para ser enviado diretamente ao assistente.
- Se o pedido parecer ser de user stories, usa "inferred_mode" = "userstory". Caso contrário, "general".
- Responde apenas em JSON válido segundo o schema.

Transcrição:
\"\"\"{cleaned}\"\"\"
""".strip()

    try:
        raw = await llm_simple(
            prompt,
            tier="standard",
            max_tokens=350,
            response_format=SPEECH_PROMPT_NORMALIZATION_SCHEMA,
        )
        parsed = _parse_json_payload(raw)
    except Exception:
        return _fallback_response(cleaned, requested_mode)

    normalized_prompt = clean_spoken_transcript(parsed.get("normalized_prompt", "")) or cleaned
    confidence = str(parsed.get("confidence", "medium") or "medium").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    inferred_mode = _guess_mode(normalized_prompt, str(parsed.get("inferred_mode", requested_mode)))
    notes = [
        clean_spoken_transcript(str(note or ""))
        for note in (parsed.get("notes") or [])
        if str(note or "").strip()
    ]

    return {
        "raw_transcript": cleaned,
        "normalized_prompt": normalized_prompt,
        "confidence": confidence,
        "inferred_mode": inferred_mode,
        "notes": notes[:5],
    }
