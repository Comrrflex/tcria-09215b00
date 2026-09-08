from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "audit_accusation_bundle_with_tcr_gateway.py"
PDF_SCRIPT = REPO_ROOT / "generate_accusation_bundle_audit_report_pdf.py"
UPLOAD_DIR = REPO_ROOT / "output" / "_uploads"
OUT_DIR = REPO_ROOT / "output" / "audit"
WHATSAPP = "https://wa.me/5521997875539"

GRAY_CSS = """
<style>
  .stApp {
    background: linear-gradient(180deg, #0B0F14 0%, #111827 40%, #0F172A 100%);
    color: #E5E7EB;
  }
  .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 980px;
  }
  .tcria-hero {
    border: 1px solid #374151;
    background: rgba(31, 41, 55, 0.72);
    border-radius: 18px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1.25rem;
    box-shadow: 0 18px 50px rgba(0,0,0,0.28);
  }
  .tcria-kicker {
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-size: 0.72rem;
    color: #9CA3AF;
    margin-bottom: 0.55rem;
  }
  .tcria-title {
    font-size: 2.1rem;
    font-weight: 700;
    color: #F3F4F6;
    margin: 0 0 0.45rem 0;
    line-height: 1.15;
  }
  .tcria-sub {
    color: #9CA3AF;
    font-size: 1.02rem;
    margin: 0 0 1rem 0;
  }
  .tcria-steps {
    color: #D1D5DB;
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0;
  }
  .tcria-meta {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin: 0.85rem 0 0.2rem;
  }
  .tcria-chip {
    border: 1px solid #4B5563;
    background: #111827;
    color: #D1D5DB;
    border-radius: 999px;
    padding: 0.28rem 0.7rem;
    font-size: 0.78rem;
  }
  div[data-testid="stFileUploader"] section {
    border: 1px dashed #6B7280 !important;
    background: #111827 !important;
    border-radius: 14px !important;
  }
  .stButton > button[kind="primary"] {
    background: #6B7280 !important;
    border: 1px solid #9CA3AF !important;
    color: #F9FAFB !important;
    border-radius: 12px !important;
    font-weight: 650 !important;
  }
</style>
"""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


def _safe_extract_zip(zip_path: Path, dest: Path) -> int:
    """Extract ZIP without path-traversal; returns file count."""
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name or name.endswith("/"):
                continue
            # block zip-slip
            target = (dest / name).resolve()
            if not str(target).startswith(str(dest.resolve())):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            count += 1
    return count


def _ocr_ready() -> bool:
    return shutil.which("tesseract") is not None


def _summarize_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    statuses = {}
    for group in ("accusation_set", "non_accusation_set"):
        for rec in data.get(group) or []:
            stt = rec.get("extraction_status") or "unknown"
            statuses[stt] = statuses.get(stt, 0) + 1
    return {
        "total": data.get("total_files_scanned"),
        "accusation": data.get("accusation_set_count"),
        "extraction": statuses,
    }


def _show_downloads(result: dict) -> None:
    st.success("Trilha concluída — baixe os 3 outputs abaixo (não some no refresh).")
    summary = result.get("summary") or {}
    if summary:
        st.caption(
            f"Arquivos: {summary.get('total')} · acusatório: {summary.get('accusation')} · "
            f"extração: {summary.get('extraction')}"
        )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "JSON",
            data=result["json_bytes"],
            file_name=result["json_name"],
            mime="application/json",
            use_container_width=True,
            key="dl_json",
        )
    with c2:
        st.download_button(
            "Markdown",
            data=result["md_bytes"],
            file_name=result["md_name"],
            mime="text/markdown",
            use_container_width=True,
            key="dl_md",
        )
    with c3:
        if result.get("pdf_bytes"):
            st.download_button(
                "PDF",
                data=result["pdf_bytes"],
                file_name=result["pdf_name"],
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf",
            )
        else:
            st.warning("PDF indisponível nesta rodada")
    if result.get("log"):
        with st.expander("Log da trilha", expanded=False):
            st.code(result["log"])


def render() -> None:
    st.set_page_config(page_title="TCRIA", layout="wide", page_icon="▣")
    st.markdown(GRAY_CSS, unsafe_allow_html=True)

    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    st.markdown(
        """
        <div class="tcria-hero">
          <div class="tcria-kicker">Relatórios auditáveis</div>
          <div class="tcria-title">TCRIA</div>
          <p class="tcria-sub">Trilha clássica de custódia — hash por bundle, o que passa não volta.</p>
          <p class="tcria-steps">
            1. Sobe o ZIP (500+ documentos)<br/>
            2. A trilha gera <strong>JSON</strong>, <strong>MD</strong> e <strong>PDF</strong><br/>
            3. OCR · sem alucinação no meio do caminho
          </p>
          <div class="tcria-meta">
            <span class="tcria-chip">cadeia de custódia</span>
            <span class="tcria-chip">rastreabilidade</span>
            <span class="tcria-chip">governança</span>
            <span class="tcria-chip">auditabilidade</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.link_button("Quero comprar / WhatsApp", WHATSAPP)

    if _ocr_ready():
        st.caption("OCR: tesseract disponível")
    else:
        st.error("OCR indisponível neste ambiente (tesseract). Imagens/PDFs escaneados não serão lidos.")

    strict = st.checkbox("Modo strict (DecisionRecord explícito)", value=True)
    up = st.file_uploader("ZIP com os documentos", type=["zip"])
    run = st.button("Rodar auditoria", type="primary", disabled=up is None, use_container_width=True)

    if run and up is not None:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        safe_name = Path(up.name).name.replace(" ", "_")
        if not safe_name.lower().endswith(".zip"):
            safe_name += ".zip"
        zip_path = UPLOAD_DIR / safe_name
        zip_path.write_bytes(up.getbuffer())

        extract_dir = UPLOAD_DIR / f"{zip_path.stem}_extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        try:
            n_files = _safe_extract_zip(zip_path, extract_dir)
        except zipfile.BadZipFile:
            st.error("ZIP inválido ou corrompido.")
            return
        if n_files == 0:
            st.error("ZIP sem arquivos utilizáveis.")
            return
        st.info(f"ZIP ok — {n_files} arquivos extraídos.")

        stem = "tcria_audit"
        cmd = [
            sys.executable,
            str(AUDIT_SCRIPT),
            "--path",
            str(extract_dir),
            "--output-stem",
            stem,
        ]
        if strict:
            cmd.append("--strict")

        with st.spinner("Trilha clássica rodando…"):
            proc = _run(cmd)

        log = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        if proc.returncode != 0:
            st.error("A trilha falhou.")
            st.code(log or "(sem log)")
            return

        suffix = "_strict" if strict else ""
        json_out = OUT_DIR / f"{stem}{suffix}.json"
        md_out = OUT_DIR / f"{stem}{suffix}.md"
        pdf_out = OUT_DIR / f"{stem}{suffix}_report.pdf"

        if not json_out.exists() or not md_out.exists():
            st.error("JSON/MD não foram gerados.")
            st.code(log or "(sem log)")
            return

        pdf_bytes = None
        pdf_proc = _run(
            [
                sys.executable,
                str(PDF_SCRIPT),
                "--input",
                str(json_out),
                "--output",
                str(pdf_out),
                "--title",
                "TCRIA — Relatório de auditoria",
            ]
        )
        if pdf_proc.returncode == 0 and pdf_out.exists():
            pdf_bytes = pdf_out.read_bytes()
        else:
            log += "\n\n[pdf]\n" + (pdf_proc.stdout or "") + "\n" + (pdf_proc.stderr or "")

        st.session_state.last_result = {
            "json_bytes": json_out.read_bytes(),
            "json_name": json_out.name,
            "md_bytes": md_out.read_bytes(),
            "md_name": md_out.name,
            "pdf_bytes": pdf_bytes,
            "pdf_name": pdf_out.name,
            "summary": _summarize_json(json_out),
            "log": log,
        }

    if st.session_state.last_result:
        _show_downloads(st.session_state.last_result)
    else:
        st.caption("Suba um ZIP e rode a auditoria para baixar os 3 outputs.")

    st.divider()
    st.markdown(f"Pronto para a empresa? [WhatsApp]({WHATSAPP})")


if __name__ == "__main__":
    render()
