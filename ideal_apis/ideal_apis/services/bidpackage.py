from __future__ import annotations

from pathlib import Path
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.exceptions import MissingAPIKeyError
from ideal_apis.http import HTTPClient


class BidPackageService:
    """Assemble and paginate bid packages with iLovePDF.

    An ITB response is a transmittal, forms, bond, license, insurance, and SOV
    assembled in a mandated order and paginated. Responsiveness failures are often
    assembly failures rather than pricing failures, so this is worth automating.

    Every operation follows iLovePDF's task flow: authenticate, start a task on an
    assigned worker, upload each file, process, download.
    """

    AUTH = "https://api.ilovepdf.com/v1/auth"
    START = "https://api.ilovepdf.com/v1/start"

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings
        self._token: str | None = None

    # ---------- task plumbing ----------

    def _authenticate(self) -> str:
        if self._token:
            return self._token
        if not self.settings.ilovepdf_public_key:
            raise MissingAPIKeyError("iLovePDF", "IDEAL_ILOVEPDF_PUBLIC_KEY")
        payload = self.http.post(
            self.AUTH,
            service="iLovePDF",
            json={"public_key": self.settings.ilovepdf_public_key},
        )
        self._token = payload["token"]
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._authenticate()}"}

    def _start(self, tool: str) -> tuple[str, str]:
        """Begin a task; returns the assigned worker host and the task id."""
        payload = self.http.get(f"{self.START}/{tool}", service="iLovePDF", headers=self._headers())
        return payload["server"], payload["task"]

    def _upload(self, server: str, task: str, path: Path) -> str:
        with path.open("rb") as handle:
            payload = self.http.post(
                f"https://{server}/v1/upload",
                service="iLovePDF",
                headers=self._headers(),
                data={"task": task},
                files={"file": (path.name, handle, "application/pdf")},
            )
        return payload["server_filename"]

    def _process(
        self,
        server: str,
        task: str,
        tool: str,
        uploaded: list[tuple[str, str]],
        **options: Any,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"task": task, "tool": tool}
        for index, (server_filename, original) in enumerate(uploaded):
            data[f"files[{index}][server_filename]"] = server_filename
            data[f"files[{index}][filename]"] = original
        data.update({k: v for k, v in options.items() if v is not None})
        return self.http.post(
            f"https://{server}/v1/process",
            service="iLovePDF",
            headers=self._headers(),
            data=data,
        )

    def _download(self, server: str, task: str, out_path: Path) -> Path:
        content = self.http.request(
            "GET",
            f"https://{server}/v1/download/{task}",
            service="iLovePDF",
            headers=self._headers(),
            raw=True,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(content)
        return out_path

    def _run(
        self,
        tool: str,
        paths: list[str | Path],
        out_path: str | Path,
        **options: Any,
    ) -> dict[str, Any]:
        sources = [Path(p) for p in paths]
        missing = [str(p) for p in sources if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"iLovePDF input not found: {', '.join(missing)}")

        server, task = self._start(tool)
        uploaded = [(self._upload(server, task, p), p.name) for p in sources]
        result = self._process(server, task, tool, uploaded, **options)
        written = self._download(server, task, Path(out_path))
        return {
            "tool": tool,
            "task": task,
            "inputs": [str(p) for p in sources],
            "output": str(written),
            "bytes": written.stat().st_size,
            "download_filename": result.get("download_filename"),
        }

    # ---------- operations ----------

    def merge(self, paths: list[str | Path], out_path: str | Path) -> dict[str, Any]:
        """Merge PDFs in the order given — the order the solicitation mandates."""
        if len(paths) < 2:
            raise ValueError("merge needs at least two input PDFs")
        return self._run("merge", paths, out_path)

    def add_page_numbers(
        self,
        path: str | Path,
        out_path: str | Path,
        *,
        starting_number: int = 1,
        vertical_position: str = "bottom",
        horizontal_position: str = "right",
    ) -> dict[str, Any]:
        """Paginate an assembled package, which most bid forms require."""
        return self._run(
            "pagenumber",
            [path],
            out_path,
            starting_number=starting_number,
            vertical_position=vertical_position,
            horizontal_position=horizontal_position,
        )

    def split(
        self,
        path: str | Path,
        out_path: str | Path,
        *,
        ranges: str,
    ) -> dict[str, Any]:
        """Pull page ranges out of a plan set or spec book, e.g. ranges="1-12,40-52"."""
        return self._run("split", [path], out_path, split_mode="ranges", ranges=ranges)

    def assemble(
        self,
        paths: list[str | Path],
        out_path: str | Path,
        *,
        starting_number: int = 1,
    ) -> dict[str, Any]:
        """Merge then paginate in one call — the full bid-package assembly step."""
        merged = Path(out_path).with_suffix(".merged.pdf")
        merge_result = self.merge(paths, merged)
        number_result = self.add_page_numbers(
            merged, out_path, starting_number=starting_number
        )
        merged.unlink(missing_ok=True)
        return {
            "inputs": merge_result["inputs"],
            "output": number_result["output"],
            "bytes": number_result["bytes"],
            "pages_numbered_from": starting_number,
        }
