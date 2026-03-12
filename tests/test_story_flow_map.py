from story_flow_map import search_story_flow_map, serialize_story_flow_match


def test_story_flow_map_surfaces_pagamentos_transferencias_seed():
    result = search_story_flow_map(
        objective="Confirmar uma transferência recorrente com CTA primário e resumo final.",
        context="Fluxo de pagamentos recorrentes e transferências.",
        epic_or_feature="Transferências recorrentes",
        dominant_domain="Pagamentos",
        top=4,
    )

    assert result["matches"]
    labels = [
        (
            str(item.get("domain", "") or ""),
            str(item.get("journey", "") or ""),
            str(item.get("flow", "") or ""),
        )
        for item in result["matches"]
    ]
    assert any(domain == "Pagamentos" and ("transfer" in journey.lower() or "recorr" in flow.lower()) for domain, journey, flow in labels)


def test_serialize_story_flow_match_avoids_repeated_title_segments():
    result = search_story_flow_map(
        objective="Dashboard com resumo e agenda.",
        context="Cards principais e agenda.",
        epic_or_feature="Dashboard",
        dominant_domain="Dashboard",
        top=3,
    )

    assert result["matches"]
    serialized = [serialize_story_flow_match(item) for item in result["matches"]]
    assert any(item["title"] == "agenda" or "Agenda" in item["title"] for item in serialized)
    assert all(" · " not in item["title"] or len({part.strip().lower() for part in item["title"].split(" · ")}) > 1 for item in serialized)
