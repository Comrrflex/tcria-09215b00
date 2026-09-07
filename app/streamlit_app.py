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


def _pretty_report_with_ai(audit_json: Path, out_md: Path) -> str:
    """AI only at the end: turn the audit JSON into a short beautiful report. No AI in the trail."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Defina OPENAI_API_KEY no Render para o relatório bonito com IA.")

    from openai import OpenAI

    payload = json.loads(audit_json.read_text(encoding="utf-8"))
    # Keep prompt small: summary fields + top accusation items only
    slim = {
        "generated_at": payload.get("generated_at"),
        "total_files_scanned": payload.get("total_files_scanned"),
        "accusation_set_count": payload.get("accusation_set_count"),
        "classification_counts": payload.get("classification_counts"),
        "compliance_gate_mode": payload.get("compliance_gate_mode"),
        "accusation_set": [
            {
                "file_name": r.get("file_name"),
                "classification": r.get("classification"),
                "overall_outcome": r.get("overall_outcome"),
                "classification_reasons": r.get("classification_reasons"),
                "gates": r.get("gates"),
            }
            for r in (payload.get("accusation_set") or [])[:40]
        ],
    }

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=os.getenv("TCRIA_REPORT_MODEL", "gpt-4.1-mini"),
        messages=[
            {
                "role": "system",
                "content": (
                    "Você escreve um relatório executivo curto e vendável em português do Brasil. "
                    "Baseie-se SOMENTE no JSON de auditoria TCRIA. Não invente fatos. "
                    "Estrutura fixa em Markdown:\n"
                    "# Relatório executivo TCRIA\n"
                    "## O que foi auditado\n"
                    "## Onde a empresa erra (achados)\n"
                    "## Por que isso importa\n"
                    "## Próximos passos recomendados\n"
                    "Tom: claro, técnico, sem juridiquês vazio. Máximo ~3 páginas."
                ),
            },
            {
                "role": "user",
                "content": "Gere o relatório a partir deste JSON de auditoria:\n\n"
                + json.dumps(slim, ensure_ascii=False, indent=2),
            },
        ],
        temperature=0.2,
    )
    text = (completion.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("A IA retornou relatório vazio.")
    out_md.write_text(text + "\n", encoding="utf-8")
    return text


def render() -> None:
    st.set_page_config(page_title="TCRIA", layout="wide")

    st.title("TCRIA")
    st.subheader("Trilha de auditoria documental — difícil de enganar")
    st.markdown(
        """
**Para empresas desconfiadas de IA.** O motor é clássico: confronta documentos,
datas, pedaços e sinais. Não inventa tese no meio do caminho.

1. Você sobe o bundle  
2. A trilha gera **JSON**, **MD** e **PDF**  
3. Só no fim, se quiser, uma IA monta um **relatório bonito**
        """
    )
    st.link_button("Quero comprar / falar no WhatsApp", WHATSAPP)

    st.divider()
    st.header("Demo")
    strict = st.checkbox("Modo strict (DecisionRecord explícito)", value=True)
    use_ai = st.checkbox(
        "No fim: gerar relatório bonito com IA (só depois da trilha)",
        value=False,
        help="Usa OPENAI_API_KEY. A IA não entra na auditoria — só resume o JSON.",
    )

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

    if use_ai:
        pretty_path = OUT_DIR / f"{stem}{suffix}_relatorio_bonito.md"
        try:
            with st.spinner("IA só no fim — relatório bonito…"):
                text = _pretty_report_with_ai(json_out, pretty_path)
            st.subheader("Relatório bonito (IA no fim)")
            st.markdown(text)
            st.download_button(
                "Baixar relatório bonito (.md)",
                data=pretty_path.read_bytes(),
                file_name=pretty_path.name,
                mime="text/markdown",
            )
        except Exception as exc:  # noqa: BLE001 — show product error to buyer/demo
            st.error(f"Relatório bonito não rodou: {exc}")

    st.divider()
    st.markdown(f"Pronto para usar na sua empresa? [Fale no WhatsApp]({WHATSAPP})")


if __name__ == "__main__":
    render()
