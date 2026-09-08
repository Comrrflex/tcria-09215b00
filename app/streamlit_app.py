from __future__ import annotations

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
  .tcria-panel {
    border: 1px solid #374151;
    background: #1F2937;
    border-radius: 16px;
    padding: 1.25rem 1.35rem 1.1rem;
    margin-top: 0.5rem;
  }
  .tcria-panel h3 {
    margin: 0 0 0.75rem 0;
    color: #F3F4F6;
    font-size: 1.05rem;
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
  .stButton > button[kind="primary"]:hover {
    background: #9CA3AF !important;
    color: #111827 !important;
  }
  a[data-testid="baseButton-secondary"], .stLinkButton > a {
    border-radius: 12px !important;
    border: 1px solid #6B7280 !important;
    background: transparent !important;
    color: #E5E7EB !important;
  }
</style>
"""


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))


def render() -> None:
    st.set_page_config(page_title="TCRIA", layout="wide", page_icon="▣")
    st.markdown(GRAY_CSS, unsafe_allow_html=True)

    st.markdown(
        """
        <div class="tcria-hero">
          <div class="tcria-kicker">Relatórios auditáveis</div>
          <div class="tcria-title">TCRIA</div>
          <p class="tcria-sub">Trilha clássica de custódia — hash por bundle, o que passa não volta.</p>
          <p class="tcria-steps">
            1. Sobe o ZIP (500+ documentos)<br/>
            2. A trilha gera <strong>JSON</strong>, <strong>MD</strong> e <strong>PDF</strong><br/>
            3. OCR bom · sem alucinação no meio do caminho
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

    st.markdown('<div class="tcria-panel"><h3>Demo</h3></div>', unsafe_allow_html=True)

    strict = st.checkbox("Modo strict (DecisionRecord explícito)", value=True)
    up = st.file_uploader("ZIP com os documentos", type=["zip"])
    run = st.button("Rodar auditoria", type="primary", disabled=up is None, use_container_width=True)

    if not run:
        st.caption("Suba um ZIP e rode a auditoria para baixar os 3 outputs.")
        return

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    zip_path = UPLOAD_DIR / up.name
    zip_path.write_bytes(up.getbuffer())
    extract_dir = UPLOAD_DIR / f"{zip_path.stem}_extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

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

    with st.expander("Log da trilha", expanded=False):
        st.code(proc.stdout or "(sem stdout)")
        if proc.stderr:
            st.code(proc.stderr)

    if proc.returncode != 0:
        st.error("A trilha falhou. Veja o log acima.")
        return

    suffix = "_strict" if strict else ""
    json_out = OUT_DIR / f"{stem}{suffix}.json"
    md_out = OUT_DIR / f"{stem}{suffix}.md"
    pdf_out = OUT_DIR / f"{stem}{suffix}_report.pdf"

    if not json_out.exists() or not md_out.exists():
        st.error("JSON/MD não foram gerados.")
        return

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
    if pdf_proc.returncode != 0 or not pdf_out.exists():
        st.warning("PDF técnico não gerou. JSON e MD estão ok.")
        with st.expander("Log PDF"):
            st.code((pdf_proc.stdout or "") + "\n" + (pdf_proc.stderr or ""))

    st.success("Trilha concluída — 3 outputs")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "JSON",
            data=json_out.read_bytes(),
            file_name=json_out.name,
            mime="application/json",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "Markdown",
            data=md_out.read_bytes(),
            file_name=md_out.name,
            mime="text/markdown",
            use_container_width=True,
        )
    with c3:
        if pdf_out.exists():
            st.download_button(
                "PDF",
                data=pdf_out.read_bytes(),
                file_name=pdf_out.name,
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.write("PDF indisponível")

    st.divider()
    st.markdown(f"Pronto para a empresa? [WhatsApp]({WHATSAPP})")


if __name__ == "__main__":
    render()
