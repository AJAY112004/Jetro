from __future__ import annotations

from pathlib import Path

from app import app


def test_api_auth_analyse_download_pdf():
    client = app.test_client()

    token_resp = client.get("/api/auth/token")
    assert token_resp.status_code == 200
    token_js = token_resp.get_json()
    assert token_js["success"] is True
    token = token_js["data"]["token"]
    assert token

    headers = {"Authorization": f"Bearer {token}"}
    sample = Path("data") / "sample_statement.csv"

    with sample.open("rb") as f:
        analyse_resp = client.post(
            "/api/analyse",
            headers=headers,
            data={"statement": (f, sample.name)},
            content_type="multipart/form-data",
        )

    assert analyse_resp.status_code == 200
    analyse_js = analyse_resp.get_json()
    assert analyse_js["success"] is True

    report = analyse_js["data"]["report"]
    assert "spend_summary" in report
    assert "category_breakdown" in report

    pdf_resp = client.get("/api/download-pdf", headers=headers)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content_type == "application/pdf"
    assert pdf_resp.data[:4] == b"%PDF"

