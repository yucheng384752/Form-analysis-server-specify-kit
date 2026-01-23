from __future__ import annotations

import argparse
from pathlib import Path

import requests


def _ensure_pdf_paths(paths: list[str]) -> list[Path]:
    pdfs: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            pdfs.extend(sorted(path.glob("*.pdf")))
        else:
            pdfs.append(path)
    return pdfs


def _default_out_zip() -> Path:
    return Path(__file__).resolve().parent / "client_data" / "results.zip"


def call_process(
    base_url: str,
    table: str,
    pdf_paths: list[Path],
    *,
    llm_url: str | None = None,
    llm_timeout: float | None = None,
    out_zip: Path,
):
    url = f"{base_url.rstrip('/')}/process"
    data = {"table": table}
    if llm_url:
        data["llm_url"] = llm_url
    if llm_timeout is not None:
        data["llm_timeout"] = str(llm_timeout)

    opened = []
    files = []
    content: bytes
    try:
        for p in pdf_paths:
            if not p.exists() or not p.is_file():
                raise FileNotFoundError(f"找不到 PDF 檔案: {p}")
            f = p.open("rb")
            opened.append(f)
            files.append(("files", (p.name, f, "application/pdf")))

        resp = requests.post(url, data=data, files=files, timeout=600)
        resp.raise_for_status()
        content = resp.content
    finally:
        for f in opened:
            try:
                f.close()
            except Exception:
                pass

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    out_zip.write_bytes(content)
    print(f"下載完成: {out_zip}")


def call_upload(base_url: str, pdf_path: Path):
    url = f"{base_url.rstrip('/')}/api/upload/pdf"
    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"找不到 PDF 檔案: {pdf_path}")
    with pdf_path.open("rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        resp = requests.post(url, files=files, timeout=60)
    resp.raise_for_status()
    print(resp.json())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_url", default="http://192.168.178.151:8000", help="server base URL")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_process = sub.add_parser("process", help="呼叫 /process")
    p_process.add_argument("--table", required=True, help="P1/P2/P3", default="P2")
    p_process.add_argument("--pdf", required=True, nargs="+", help="PDF 檔案或資料夾", default="PDF/P2")
    p_process.add_argument("--llm_url", required=False, help="LLM URL")
    p_process.add_argument("--llm_timeout", required=False, type=float, help="LLM timeout 秒")
    p_process.add_argument(
        "--out",
        required=False,
        default=str(_default_out_zip()),
        help="輸出 zip 路徑",
    )

    p_upload = sub.add_parser("upload", help="呼叫 /api/upload/pdf")
    p_upload.add_argument("--pdf", required=True, help="PDF 檔案")

    args = parser.parse_args()

    if args.cmd == "process":
        pdf_paths = _ensure_pdf_paths(args.pdf)
        if not pdf_paths:
            raise SystemExit("找不到 PDF 檔案")
        call_process(
            args.base_url,
            args.table,
            pdf_paths,
            llm_url=args.llm_url,
            llm_timeout=args.llm_timeout,
            out_zip=Path(args.out).expanduser().resolve(),
        )
    elif args.cmd == "upload":
        call_upload(args.base_url, Path(args.pdf))


if __name__ == "__main__":
    main()

