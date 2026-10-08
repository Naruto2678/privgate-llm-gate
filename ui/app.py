"""Streamlit demo.  Run from the project root:  streamlit run ui/app.py"""

from __future__ import annotations

import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so `import privgate` works when launched by Streamlit

import streamlit as st  # noqa: E402

from privgate.config import get_api_key, load_config  # noqa: E402
from privgate.errors import PrivGateError  # noqa: E402
from privgate.gateway import Gateway  # noqa: E402
from privgate.llm import build_client, list_tasks  # noqa: E402
from privgate.ner import spacy_available  # noqa: E402

COLORS = {
    "PERSON": "#ffd6a5", "PHONE": "#caffbf", "EMAIL": "#9bf6ff", "AADHAAR": "#ffadad", "PAN": "#ffc6ff",
    "CREDIT_CARD": "#fdffb6", "BANK_ACCOUNT": "#bdb2ff", "IFSC": "#a0c4ff", "UPI_ID": "#b9fbc0", "PIN_CODE": "#d0f4de",
}  # fmt: skip

st.set_page_config(page_title="PrivGate", page_icon="🛡️", layout="wide")
st.title("🛡️ PrivGate - privacy gateway for LLMs")
st.caption("Personal data is removed on your machine BEFORE the text goes to the LLM, and put back in the answer.")

cfg = load_config()
with st.sidebar:
    st.subheader("Detection settings")
    st.caption("Turn these off to see what each idea adds.")
    use_checksums = st.toggle("Checksums (Aadhaar, card, PAN)", value=cfg.privacy.use_checksums)
    use_context = st.toggle("Context rules (A/C, PIN, names)", value=cfg.privacy.use_context_rules)
    ner_ok = spacy_available()
    use_spacy = st.toggle("spaCy name detection", value=False, disabled=not ner_ok,
                          help=None if ner_ok else "Not installed - see README.")  # fmt: skip
    restore_reply = st.toggle("Restore real values in the answer", value=cfg.privacy.restore_in_reply)
    st.divider()
    st.write(f"Provider: `{cfg.llm.provider}`  |  Model: `{cfg.llm.model}`")
    st.success("API key found") if get_api_key(cfg.llm.provider) else st.warning("No API key (redaction still works).")
    st.caption("Only the redacted text is sent to the LLM. Audit logs contain counts only.")

cfg.privacy = cfg.privacy.model_copy(update={
    "use_checksums": use_checksums, "use_context_rules": use_context,
    "use_spacy_ner": use_spacy, "restore_in_reply": restore_reply, "audit_log_path": None,
})  # fmt: skip

samples = {p.stem.replace("_", " ").title(): p for p in sorted((ROOT / "samples").glob("*.txt"))}
choice = st.selectbox("Load a sample message (optional)", ["-"] + list(samples))
if choice != "-":
    st.session_state["text"] = samples[choice].read_text(encoding="utf-8")

text = st.text_area("Message (may contain personal data)", key="text", height=220)
task = st.selectbox("What should the LLM do?", list_tasks())
col1, col2 = st.columns(2)
only_redact = col1.button("1) Redact only (no API call)", disabled=not text.strip())
ask_llm = col2.button("2) Redact + ask the LLM", type="primary", disabled=not text.strip())


def highlight(raw: str, entities) -> str:
    out, cursor = [], 0
    for e, placeholder in entities:
        out.append(html.escape(raw[cursor : e.start]))
        color = COLORS.get(e.type, "#eee")
        out.append(f'<mark style="background:{color};padding:1px 3px;border-radius:3px" title="{e.detector}">'
                   f"{html.escape(raw[e.start : e.end])}<sub> {placeholder}</sub></mark>")  # fmt: skip
        cursor = e.end
    out.append(html.escape(raw[cursor:]))
    return "<div style='white-space:pre-wrap;line-height:1.7'>" + "".join(out) + "</div>"


if only_redact or ask_llm:
    try:
        gateway = Gateway(cfg, build_client(cfg) if ask_llm else None)
        red = gateway.sanitize(text)
        result = None
        if ask_llm:
            with st.spinner("Calling the LLM with the redacted text..."):
                result = gateway.run(task, text)
    except PrivGateError as exc:
        st.error(str(exc))
        st.stop()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    st.subheader(f"Found {len(red.entities)} personal value(s)")
    left, right = st.columns(2)
    with left:
        st.markdown("**Your message** (highlighted)")
        st.markdown(highlight(text, red.entities), unsafe_allow_html=True)
    with right:
        st.markdown("**What the LLM receives**")
        st.code(red.redacted_text, language=None)
    if red.entities:
        st.dataframe(
            [{"Placeholder": ph, "Type": e.type, "Found by": e.detector, "Masked value": Gateway._entities_out(red, False)[i].masked_value}
             for i, (e, ph) in enumerate(red.entities)],
            hide_index=True,
        )  # fmt: skip

    if result:
        st.subheader("LLM answer")
        a, b = st.columns(2)
        a.markdown("**As received (placeholders)**")
        a.write(result.reply_redacted)
        b.markdown("**Final answer (real values restored)**")
        b.write(result.reply)
        for w in result.warnings:
            st.warning(w)
