from __future__ import annotations

from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class DocumentsService:
    """Invoice OCR, document extraction, and PDF generation."""

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings

    def docstruct_extract(
        self,
        *,
        text: str | None = None,
        url: str | None = None,
        doc_type: str = "invoice",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": doc_type}
        if text:
            payload["text"] = text
        if url:
            payload["url"] = url
        return self.http.post(
            "https://docstruct.pages.dev/api/extract",
            service="DocStruct",
            json=payload,
        )

    def ocr_space(
        self,
        *,
        url: str | None = None,
        file_path: str | None = None,
        language: str = "eng",
    ) -> dict[str, Any]:
        if not self.settings.ocr_space_key:
            raise MissingAPIKeyError("OCR.Space", "IDEAL_OCR_SPACE_KEY")
        data: dict[str, Any] = {"language": language, "isOverlayRequired": "false"}
        if url:
            data["url"] = url
            return self.http.post(
                "https://api.ocr.space/parse/image",
                service="OCR.Space",
                data=data,
                headers={"apikey": self.settings.ocr_space_key},
            )
        if file_path:
            with open(file_path, "rb") as f:
                files = {"file": f}
                with self.http._client() as client:
                    response = client.post(
                        "https://api.ocr.space/parse/image",
                        data=data,
                        files=files,
                        headers={"apikey": self.settings.ocr_space_key},
                    )
                if response.status_code >= 400:
                    from ideal_apis.exceptions import APIRequestError

                    raise APIRequestError("OCR.Space", response.status_code, response.text[:500])
                return response.json()
        raise ValueError("Provide url or file_path for OCR")

    def buildpdf(
        self,
        html: str,
        *,
        filename: str = "document.pdf",
    ) -> bytes:
        if not self.settings.buildpdf_key:
            raise MissingAPIKeyError("BuildPDF", "IDEAL_BUILDPDF_KEY")
        with self.http._client() as client:
            response = client.post(
                "https://buildpdf.co/api/v1/pdf",
                json={"html": html, "filename": filename},
                headers={"Authorization": f"Bearer {self.settings.buildpdf_key}"},
            )
        if response.status_code >= 400:
            from ideal_apis.exceptions import APIRequestError

            raise APIRequestError("BuildPDF", response.status_code, response.text[:500])
        return response.content

    def pandadoc_list_templates(self) -> dict[str, Any]:
        if not self.settings.pandadoc_key:
            raise MissingAPIKeyError("PandaDoc", "IDEAL_PANDADOC_KEY")
        return self.http.get(
            "https://api.pandadoc.com/public/v1/templates",
            service="PandaDoc",
            headers={"Authorization": f"API-Key {self.settings.pandadoc_key}"},
        )
