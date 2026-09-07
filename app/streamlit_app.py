from __future__ import annotations

import json
import os
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


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT))




def render() -> None:
    st.set_page_config(page_title="TCRIA", layout="wide")

    st.title("TCRIA")
    st.subheader("Trilha de auditoria documental — difícil de enganar")
    st.markdown(
        """
**Para empresas desconfiadas de IA.** O motor é clássico: confronta documentos,
datas, pedaços e sinais. Não inventa tese no meio do caminho.

1. Você sobe o bundle (~50 documentos)  
2. A trilha (custódia + hash) gera **JSON**, **MD** e **PDF**  
3. Daí vemos se alguém compra
        """
    )
    st.link_button("Quero comprar / falar no WhatsApp", WHATSAPP)

    st.divider()
    st.header("Demo")
    strict = st.checkbox("Modo strict (DecisionRecord explícito)", value=True)
    up = st.file_uploader("Upload do ZIP com os documentos", type=["zip"])
    run = st.button("Rodar auditoria", type="primary", disabled=up is None)

    if not run:
        st.info("Suba um ZIP e rode a auditoria para ver os 3 outputs.")
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
        st.download_button("JSON", data=json_out.read_bytes(), file_name=json_out.name, mime="application/json")
    with c2:
        st.download_button("Markdown", data=md_out.read_bytes(), file_name=md_out.name, mime="text/markdown")
    with c3:
        if pdf_out.exists():
            st.download_button("PDF técnico", data=pdf_out.read_bytes(), file_name=pdf_out.name, mime="application/pdf")
        else:
            st.write("PDF indisponível")

    st.divider()
    st.markdown(f"Pronto para usar na sua empresa? [Fale no WhatsApp]({WHATSAPP})")


if __name__ == "__main__":
    render()
