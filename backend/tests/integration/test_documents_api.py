"""Document API endpoints against the real app + a real database.
See specs/TESTING.md §3 and specs/API.md §2.

With httpx's ASGITransport, `BackgroundTasks` run synchronously within the
request call - no polling needed to observe post-upload processing.
"""

from io import BytesIO

from httpx import AsyncClient
from pypdf import PdfWriter


def _blank_pdf_bytes() -> bytes:
    """A syntactically valid PDF with no text layer - exercises the
    scanned/image-only-PDF failure path (specs/RAG_PIPELINE.md §1.2)."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestUploadDocument:
    async def test_upload_txt_returns_202_and_completes_processing(
        self, client: AsyncClient
    ) -> None:
        files = {"file": ("notes.txt", b"Hello world.\n\nThis is a test document.", "text/plain")}
        response = await client.post("/api/v1/documents", files=files)

        assert response.status_code == 202
        body = response.json()
        assert body["original_filename"] == "notes.txt"
        assert body["content_type"] == "text/plain"
        assert body["status"] == "pending"

        detail = await client.get(f"/api/v1/documents/{body['id']}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "completed"

    async def test_upload_rejects_disallowed_extension(self, client: AsyncClient) -> None:
        files = {"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")}
        response = await client.post("/api/v1/documents", files=files)

        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"

    async def test_upload_rejects_content_extension_mismatch(self, client: AsyncClient) -> None:
        files = {"file": ("fake.pdf", b"not actually a pdf", "application/pdf")}
        response = await client.post("/api/v1/documents", files=files)

        assert response.status_code == 400
        assert response.json()["error_code"] == "UNSUPPORTED_FILE_TYPE"

    async def test_upload_marks_pdf_with_no_text_layer_as_failed(self, client: AsyncClient) -> None:
        files = {"file": ("scan.pdf", _blank_pdf_bytes(), "application/pdf")}
        response = await client.post("/api/v1/documents", files=files)
        assert response.status_code == 202

        detail = await client.get(f"/api/v1/documents/{response.json()['id']}")
        assert detail.json()["status"] == "failed"
        assert detail.json()["error_message"] is not None


class TestListDocuments:
    async def test_list_returns_uploaded_documents(self, client: AsyncClient) -> None:
        await client.post(
            "/api/v1/documents", files={"file": ("a.txt", b"content a", "text/plain")}
        )
        await client.post(
            "/api/v1/documents", files={"file": ("b.txt", b"content b", "text/plain")}
        )

        response = await client.get("/api/v1/documents")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert {item["original_filename"] for item in body["items"]} == {"a.txt", "b.txt"}

    async def test_list_filters_by_status(self, client: AsyncClient) -> None:
        await client.post("/api/v1/documents", files={"file": ("ok.txt", b"content", "text/plain")})
        await client.post(
            "/api/v1/documents", files={"file": ("scan.pdf", _blank_pdf_bytes(), "application/pdf")}
        )

        completed = await client.get("/api/v1/documents", params={"status": "completed"})
        failed = await client.get("/api/v1/documents", params={"status": "failed"})

        assert completed.json()["total"] == 1
        assert completed.json()["items"][0]["original_filename"] == "ok.txt"
        assert failed.json()["total"] == 1
        assert failed.json()["items"][0]["original_filename"] == "scan.pdf"


class TestGetDocument:
    async def test_get_nonexistent_document_returns_404(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        assert response.json()["error_code"] == "DOCUMENT_NOT_FOUND"

    async def test_get_status_endpoint_returns_minimal_payload(self, client: AsyncClient) -> None:
        upload = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", b"hello", "text/plain")}
        )
        document_id = upload.json()["id"]

        response = await client.get(f"/api/v1/documents/{document_id}/status")

        assert response.status_code == 200
        assert set(response.json().keys()) == {"id", "status", "error_message"}


class TestDeleteDocument:
    async def test_delete_removes_document(self, client: AsyncClient) -> None:
        upload = await client.post(
            "/api/v1/documents", files={"file": ("notes.txt", b"hello", "text/plain")}
        )
        document_id = upload.json()["id"]

        delete_response = await client.delete(f"/api/v1/documents/{document_id}")
        get_response = await client.get(f"/api/v1/documents/{document_id}")

        assert delete_response.status_code == 204
        assert get_response.status_code == 404

    async def test_delete_nonexistent_document_returns_404(self, client: AsyncClient) -> None:
        response = await client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
