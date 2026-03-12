from __future__ import annotations


def test_project_context_and_jobs_pages(client) -> None:
    response = client.post(
        "/projects",
        data={
            "organization_name": "GridBox Cloud",
            "organization_owner_name": "Sinan",
            "organization_plan_tier": "business",
            "name": "GridBox HeadEnd",
            "ownership_type": "company",
            "summary": "Saha haberlesme urunu",
            "primary_repo_path": r"C:\\Users\\Sinan\\source\\repos\\HayenTechnology",
            "status_value": "active",
        },
        follow_redirects=False,
    )

    project_path = response.headers["location"].split("?", 1)[0]

    context_page = client.get(f"{project_path}/context")
    assert context_page.status_code == 200
    assert "Context Studio" in context_page.text

    jobs_page = client.get(f"{project_path}/jobs")
    assert jobs_page.status_code == 200
    assert "Knowledge Jobs" in jobs_page.text

    job_response = client.post(
        f"{project_path}/jobs",
        data={"job_type": "github_scan"},
        follow_redirects=True,
    )
    assert job_response.status_code == 200
    assert "Job kuyruga alindi." in job_response.text
