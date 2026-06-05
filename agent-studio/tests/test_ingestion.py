import base64
import io

import pytest
from fastapi.testclient import TestClient

from agent_studio.config import get_settings
from agent_studio.ingestion import ExtractionError, extract_file
from agent_studio.integration_config import integration_config_store
from agent_studio.main import app, knowledge_ingestion_service, knowledge_ingestion_store
from agent_studio.schemas import KnowledgeIngestionFile
from agent_studio.store import store


client = TestClient(app)


def setup_function() -> None:
    store.clear()
    integration_config_store.clear()
    knowledge_ingestion_store.clear()
    get_settings.cache_clear()


def _base64_bytes(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def test_extractors_parse_supported_fixtures() -> None:
    markdown = extract_file(
        KnowledgeIngestionFile(filename="refund-policy.md", content="# Refund Policy\nSale items need review."),
    )
    assert markdown.title == "Refund Policy"
    assert "Sale items" in markdown.content

    transcript = extract_file(
        KnowledgeIngestionFile(
            filename="call-transcript.json",
            content='{"messages":[{"speaker":"Customer","text":"My order is late."}]}',
        ),
    )
    assert "Customer: My order is late." in transcript.content

    csv_doc = extract_file(
        KnowledgeIngestionFile(
            filename="shipping-faq.csv",
            content="Question,Answer\nWhere is my order?,Check tracking first.",
        ),
    )
    assert "Question: Where is my order?" in csv_doc.content

    docx_buffer = io.BytesIO()
    from docx import Document

    docx = Document()
    docx.add_heading("Warranty SOP", level=1)
    docx.add_paragraph("Ask for proof of purchase before warranty action.")
    docx.save(docx_buffer)
    docx_doc = extract_file(
        KnowledgeIngestionFile(
            filename="warranty-sop.docx",
            content=_base64_bytes(docx_buffer.getvalue()),
            encoding="base64",
        ),
    )
    assert "proof of purchase" in docx_doc.content

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Returns"
    sheet.append(["Scenario", "Rule"])
    sheet.append(["Sale item", "Escalate before promising refund"])
    xlsx_buffer = io.BytesIO()
    workbook.save(xlsx_buffer)
    xlsx_doc = extract_file(
        KnowledgeIngestionFile(
            filename="returns.xlsx",
            content=_base64_bytes(xlsx_buffer.getvalue()),
            encoding="base64",
        ),
    )
    assert "Scenario: Sale item" in xlsx_doc.content

    pdf_doc = extract_file(
        KnowledgeIngestionFile(
            filename="policy.pdf",
            content=_base64_bytes(b"%PDF-1.4\nBT (PDF refund policy text) Tj ET\n%%EOF"),
            encoding="base64",
        ),
    )
    assert "PDF refund policy text" in pdf_doc.content


def test_scanned_pdf_without_text_reports_ocr_needed() -> None:
    with pytest.raises(ExtractionError) as exc_info:
        extract_file(
            KnowledgeIngestionFile(
                filename="scan.pdf",
                content=_base64_bytes(b"%PDF-1.4\n%%EOF"),
                encoding="base64",
            ),
        )

    assert exc_info.value.code == "ocr_required"
    assert "OCR" in exc_info.value.message


def test_ingestion_job_creates_needs_review_document() -> None:
    response = client.post(
        "/knowledge/ingestion-jobs",
        json={
            "source_name": "Test Upload",
            "files": [
                {
                    "filename": "shipping-faq.md",
                    "content": "# Shipping FAQ\nUse tracking before escalation.",
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "needs_review"
    assert payload["job"]["processed_files"] == 1
    assert payload["documents"][0]["approval_status"] == "needs_review"
    assert payload["documents"][0]["chunk_count"] == 0


def test_unapproved_document_does_not_retrieve_until_approved() -> None:
    created = client.post(
        "/knowledge/ingestion-jobs",
        json={
            "source_name": "Support Upload",
            "files": [
                {
                    "filename": "zephyrwidget-sop.md",
                    "category": "sops",
                    "content": "# ZephyrWidget SOP\nUse zephyrwidget-token before approving service credits.",
                },
            ],
        },
    ).json()
    document_id = created["documents"][0]["id"]

    before = client.post(
        "/knowledge/search-test",
        json={"query": "zephyrwidget-token", "intent": "general_support", "risk_level": "medium"},
    ).json()
    assert all("zephyrwidget" not in hit["excerpt"].lower() for hit in before["hits"])

    approved = client.post(f"/knowledge/documents/{document_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"
    assert approved.json()["chunk_count"] >= 1

    after = client.post(
        "/knowledge/search-test",
        json={"query": "zephyrwidget-token", "intent": "general_support", "risk_level": "medium"},
    ).json()
    assert any("zephyrwidget" in hit["excerpt"].lower() for hit in after["hits"])


def test_duplicate_upload_does_not_create_duplicate_active_document() -> None:
    payload = {
        "source_name": "Duplicate Upload",
        "files": [
            {
                "filename": "refund-policy.md",
                "source_path": "policies/refund-policy.md",
                "content": "# Refund Policy\nDuplicate uploads should collapse.",
            },
            {
                "filename": "refund-policy-copy.md",
                "source_path": "policies/refund-policy.md",
                "content": "# Refund Policy\nDuplicate uploads should collapse.",
            },
        ],
    }

    response = client.post("/knowledge/ingestion-jobs", json=payload)
    assert response.status_code == 200

    documents = client.get("/knowledge/documents").json()["documents"]
    matching = [
        document
        for document in documents
        if document["source_path"] == "policies/refund-policy.md"
    ]
    assert len(matching) == 1


def test_embedding_failure_returns_readable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = client.post(
        "/knowledge/ingestion-jobs",
        json={
            "source_name": "Embedding Failure Upload",
            "files": [
                {
                    "filename": "failure-sop.md",
                    "content": "# Failure SOP\nThis should fail embedding.",
                },
            ],
        },
    ).json()
    document_id = created["documents"][0]["id"]

    def fail_embed(value: str) -> list[float]:
        raise RuntimeError("OpenAI embedding request failed: ConnectError")

    monkeypatch.setattr(knowledge_ingestion_service.embedding_service, "embed_text", fail_embed)

    response = client.post(f"/knowledge/documents/{document_id}/approve")

    assert response.status_code == 502
    assert "OpenAI embedding request failed" in response.json()["detail"]
