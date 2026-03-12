from story_policy_packs import select_story_policy_pack


def test_select_story_policy_pack_prefers_pagamentos():
    policy_pack = select_story_policy_pack(
        objective="Confirmar uma transferência recorrente com CTA primário e resumo final.",
        context="Fluxo de pagamentos recorrentes e transferências.",
        epic_or_feature="Transferências recorrentes",
        dominant_domain="Pagamentos",
    )

    assert policy_pack
    assert policy_pack["domain"] == "Pagamentos"
    assert "acceptance_criteria" in policy_pack["mandatory_sections"]


def test_select_story_policy_pack_prefers_dashboard():
    policy_pack = select_story_policy_pack(
        objective="Criar user story para o dashboard com agenda e resumo operacional.",
        context="Cards principais e agenda na home.",
        epic_or_feature="Dashboard",
        dominant_domain="Dashboard",
    )

    assert policy_pack
    assert policy_pack["domain"] == "Dashboard"
    assert policy_pack["canonical_title_pattern"]
