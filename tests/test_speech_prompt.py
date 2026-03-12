from __future__ import annotations

import pytest

import speech_prompt


def test_clean_spoken_transcript_removes_fillers_and_duplicate_punctuation():
    cleaned = speech_prompt.clean_spoken_transcript("Hum ahn preciso, , comparar este ficheiro... eeh com o outro!!")

    assert cleaned == "preciso, comparar este ficheiro. eeh com o outro!"


@pytest.mark.asyncio
async def test_normalize_spoken_prompt_falls_back_when_llm_fails(monkeypatch):
    async def _boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(speech_prompt, "llm_simple", _boom)

    result = await speech_prompt.normalize_spoken_prompt(
        "Hum preciso de perceber os bugs mais críticos do MDSE",
        mode="general",
    )

    assert result["raw_transcript"] == "preciso de perceber os bugs mais críticos do MDSE"
    assert result["normalized_prompt"] == "preciso de perceber os bugs mais críticos do MDSE"
    assert result["confidence"] == "medium"
    assert result["inferred_mode"] == "general"


@pytest.mark.asyncio
async def test_normalize_spoken_prompt_uses_structured_llm_output(monkeypatch):
    async def _mock_llm(*args, **kwargs):
        return """
        {
          "normalized_prompt": "Cria uma user story para o step 2 da Via Verde com foco no resumo e confirmação.",
          "confidence": "high",
          "inferred_mode": "userstory",
          "notes": ["O pedido referia Via Verde e um step específico."]
        }
        """

    monkeypatch.setattr(speech_prompt, "llm_simple", _mock_llm)

    result = await speech_prompt.normalize_spoken_prompt(
        "olha preciso de uma user story para o step 2 da via verde resum resumo e confirmação",
        mode="general",
    )

    assert result["normalized_prompt"].startswith("Cria uma user story")
    assert result["confidence"] == "high"
    assert result["inferred_mode"] == "userstory"
    assert result["notes"] == ["O pedido referia Via Verde e um step específico."]
