from story_domain_profiles import select_story_domain_profile


def test_select_story_domain_profile_prefers_pagamentos():
    profile = select_story_domain_profile(
        objective="Confirmar uma transferência recorrente com resumo final.",
        context="Fluxo de pagamentos recorrentes e transferências.",
        epic_or_feature="Transferências recorrentes",
        dominant_domain="Pagamentos",
    )

    assert profile
    assert profile["domain"] == "Pagamentos"
    assert "Pagamentos" in profile["design_file_title"]


def test_select_story_domain_profile_prefers_dashboard():
    profile = select_story_domain_profile(
        objective="Criar story para o dashboard com agenda e resumo operacional.",
        context="Cards principais e agenda na home.",
        epic_or_feature="Dashboard",
        dominant_domain="Dashboard",
    )

    assert profile
    assert profile["domain"] == "Dashboard"
    assert profile["top_journeys"]
