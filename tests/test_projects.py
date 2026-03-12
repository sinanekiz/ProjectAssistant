from __future__ import annotations


def test_projects_page_renders(client) -> None:
    response = client.get("/projects")

    assert response.status_code == 200
    assert "Cloud Assistant Studio" in response.text
    assert "Workspace Olustur" in response.text
    assert "Projeyi Olustur" in response.text


def test_project_can_be_created_with_inline_workspace(client) -> None:
    response = client.post(
        "/projects",
        data={
            "organization_name": "GridBox Cloud",
            "organization_owner_name": "Sinan",
            "organization_billing_email": "ops@gridbox.test",
            "organization_plan_tier": "business",
            "name": "GridBox HeadEnd",
            "ownership_type": "company",
            "summary": "Saha haberlesme urunu",
            "primary_repo_path": r"C:\Users\Sinan\source\repos\HayenTechnology",
            "status_value": "active",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Proje olusturuldu." in response.text
    assert "GridBox HeadEnd" in response.text
    assert "GridBox Cloud" in response.text
    assert "business" in response.text


def test_project_detail_supports_context_and_assistant_configuration(client) -> None:
    create_response = client.post(
        "/projects",
        data={
            "organization_name": "Mobitolya SaaS",
            "organization_owner_name": "Sinan",
            "organization_plan_tier": "team",
            "name": "Mobitolya",
            "ownership_type": "personal",
            "summary": "Kisisel startup",
            "primary_repo_path": r"C:\Users\Sinan\source\repos\sinanekiz\Mobitolya",
            "status_value": "active",
        },
        follow_redirects=False,
    )

    project_location = create_response.headers["location"]
    project_path = project_location.split("?", 1)[0]

    person_response = client.post(
        f"{project_path}/people",
        data={
            "name": "Rahim Ozdemir",
            "role_title": "Tech Lead",
            "relationship_type": "manager",
            "external_ref": "rahim@mobitolya.test",
            "notes": "Kisa ama teknik ozetleri sever.",
        },
        follow_redirects=True,
    )
    setting_response = client.post(
        f"{project_path}/settings",
        data={"key": "preferred_channel", "value": "whatsapp"},
        follow_redirects=True,
    )
    context_response = client.post(
        f"{project_path}/contexts",
        data={
            "title": "Ownership",
            "section": "routing",
            "content": "Bu proje kisisel startup kapsamindadir.",
            "source_type": "manual",
            "source_ref": "user-note",
        },
        follow_redirects=True,
    )
    profile_response = client.post(
        f"{project_path}/assistant-profiles",
        data={
            "display_name": "Mobitolya Growth Assistant",
            "mission": "Gelen istekleri ozetle, gerekli entegrasyonlari takip et ve branch oner.",
            "tone_profile": "Sirket ici net, musteriye guven veren ve kisa.",
            "response_constraints": "Emin olmadigi yerde once context kontrolu yapsin.",
            "escalation_policy": "Risk varsa Telegram ve Teams ile bildir.",
            "default_language": "tr",
            "execution_mode": "draft-first",
            "is_default": "true",
        },
        follow_redirects=True,
    )
    style_response = client.post(
        f"{project_path}/style-rules",
        data={
            "channel_type": "teams",
            "audience_name": "Rahim Ozdemir",
            "audience_role": "manager",
            "style_summary": "Yoneticiye kisa, risk ve aksiyon odakli cevap ver.",
            "do_guidance": "Etki ve sonraki adimi yaz.",
            "dont_guidance": "Belirsiz ifadeler kullanma.",
            "sample_reply": "Sorunu izole ettim, Jira task aciyorum ve branch onerisi hazirliyorum.",
            "source_type": "manual",
            "is_active": "true",
        },
        follow_redirects=True,
    )

    assert person_response.status_code == 200
    assert "Rahim Ozdemir" in person_response.text

    assert setting_response.status_code == 200
    assert "preferred_channel" in setting_response.text
    assert "whatsapp" in setting_response.text

    assert context_response.status_code == 200
    assert "Ownership" in context_response.text
    assert "Bu proje kisisel startup kapsamindadir." in context_response.text

    assert profile_response.status_code == 200
    assert "Assistant profili kaydedildi." in profile_response.text
    assert "Mobitolya Growth Assistant" in profile_response.text

    assert style_response.status_code == 200
    assert "Iletisim stili kaydedildi." in style_response.text
    assert "Yoneticiye kisa, risk ve aksiyon odakli cevap ver." in style_response.text
    assert "cloud assistant brief" in style_response.text
