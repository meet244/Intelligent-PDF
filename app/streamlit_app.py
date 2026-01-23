import streamlit as st
import tempfile
import os
from dotenv import load_dotenv
from app.pdf_parser import (
    extract_text_single_page,
    extract_tables_single_page,
    extract_total_pages,
    save_debug_image_single_page,
    summarize_pdf,
    summarize_page
)

# ──────────────────────── SETUP ────────────────────────
load_dotenv()

st.set_page_config(page_title="PDF Intelligence Extractor", page_icon="🧠", layout="wide")

# ──────────────────────── HEADER ────────────────────────
st.title("📄 PDF Intelligence Extractor")
st.markdown("A minimal PDF text & table parsing tool powered by **PDFPlumber** and **Gemini**. "
            "Easily extract tables, full text, and generate smart summaries per page or document.")

# ──────────────────────── FILE UPLOADER ────────────────────────
uploaded_file = st.file_uploader("📎 Upload a PDF file", type=["pdf"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        pdf_path = tmp.name

    st.session_state["pdf_path"] = pdf_path

    # ──────────────────────── TOTAL PAGES ────────────────────────
    try:
        total_pages = extract_total_pages(pdf_path)
    except Exception as e:
        st.error(f"❌ Failed to read PDF: {e}")
        st.stop()

    # ──────────────────────── TEXT EXTRACTION ────────────────────────
    if "full_text_by_page" not in st.session_state:
        st.session_state["full_text_by_page"] = {
            f"Page {i+1}": extract_text_single_page(pdf_path, i)
            for i in range(total_pages)
        }

    # ──────────────────────── FULL DOCUMENT SUMMARY ────────────────────────
    st.markdown("### 🧠 Document Summary")

    if "global_summary" not in st.session_state:
        if st.button("🪄 Generate Summary for Entire PDF"):
            with st.spinner("Running Gemini to summarize the entire document..."):
                st.session_state["global_summary"] = summarize_pdf(st.session_state["full_text_by_page"])

    if "global_summary" in st.session_state:
        st.success("Here's a quick overview of your document:")
        st.info(st.session_state["global_summary"])

    # ──────────────────────── PAGE SELECTION ────────────────────────
    st.markdown("### 📑 Select a Page to Explore")
    page_options = [f"Page {i}" for i in range(1, total_pages + 1)]
    selected_page_label = st.selectbox("Go to a specific page", page_options)
    selected_page_idx = int(selected_page_label.split(" ")[1])
    page_label = f"Page {selected_page_idx}"
    page_text = st.session_state["full_text_by_page"][page_label]

    if "last_selected_page" not in st.session_state:
        st.session_state.last_selected_page = selected_page_idx

    if selected_page_idx != st.session_state.last_selected_page:
        st.session_state.expand_text_section = False
        st.session_state.last_selected_page = selected_page_idx

    if "expand_text_section" not in st.session_state:
        st.session_state.expand_text_section = False

    # ──────────────────────── TEXT & SUMMARY SECTION ────────────────────────
    with st.expander("📘 Extracted Text", expanded=st.session_state.expand_text_section):
        col1, col2 = st.columns([1, 5])
        with col1:
            summarize_triggered = st.button("📝 Summarize This Page", key=f"summary-btn-{selected_page_idx}")

        if summarize_triggered:
            if "global_summary" not in st.session_state:
                st.warning("Please generate the full PDF summary first.")
            else:
                with st.spinner("Summarizing this page..."):
                    summary = summarize_page(page_text, context_summary=st.session_state["global_summary"])
                    st.session_state[f"page_{selected_page_idx}_summary"] = summary
                    st.session_state.expand_text_section = True

        if f"page_{selected_page_idx}_summary" in st.session_state:
            st.markdown("#### 🔍 Page Summary")
            st.info(st.session_state[f"page_{selected_page_idx}_summary"])

        st.markdown("#### 📄 Full Page Text")
        st.text(page_text)

    # ──────────────────────── TABLE EXTRACTION ────────────────────────
    with st.expander("📊 Extracted Tables", expanded=False):
        try:
            tables, strategy = extract_tables_single_page(pdf_path, selected_page_idx - 1)
        except Exception as e:
            st.error(f"❌ Error extracting tables: {e}")
            st.stop()

        strategy_color = {
            "lines": "🟢",
            "none": "🔴",
            "error": "❌",
            "unknown": "⚪️"
        }.get(strategy, "⚪️")

        st.markdown(f"**Detection Strategy:** {strategy_color} `{strategy}`")

        if tables and strategy != "none":
            for i, df in enumerate(tables):
                st.markdown(f"#### 📎 Table {i+1}")
                st.dataframe(df)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"⬇️ Download Table {i+1} (CSV)",
                    data=csv,
                    file_name=f"{page_label}_table{i+1}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No tables found on this page.")

    # ──────────────────────── DEBUG IMAGE ────────────────────────
    if st.checkbox("🖼️ Show Table Detection Preview?"):
        st.markdown(f"### 🔍 Table Preview — {page_label}")
        try:
            img_bytes = save_debug_image_single_page(pdf_path, selected_page_idx - 1)
            st.image(img_bytes, caption=f"🧩 Detected Table Layout — {page_label}")
        except Exception as e:
            st.error(f"⚠️ Could not generate preview image: {e}")

# ──────────────────────── FOOTER ────────────────────────
st.markdown("---")
st.markdown("🔧 Built with 💙 by **Miray Ozcan** | Powered by **PDFPlumber + Gemini + Streamlit**")