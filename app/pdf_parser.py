import os
import pdfplumber
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import google.generativeai as genai

# === Load API Key ===
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
client = genai.GenerativeModel("gemini-3-pro")


# === Default Table Settings ===
DEFAULT_TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 4,
    "join_tolerance": 4,
    "edge_min_length": 5,
    "intersection_tolerance": 5,
    "text_tolerance": 3,
    "text_x_tolerance": 3,
    "text_y_tolerance": 3,
}


# === Table & Text Extraction ===

def is_valid_table(table):
    if not table or not isinstance(table, list) or len(table) < 2:
        return False

    row_lengths = [len(row) for row in table]
    if max(row_lengths, default=0) < 2:
        return False

    total_cells = sum(len(row) for row in table)
    non_empty_cells = sum(1 for row in table for cell in row if cell and cell.strip())

    if total_cells == 0 or (non_empty_cells / total_cells < 0.4):
        return False

    return True


def extract_text_single_page(pdf_path, page_number):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number]
        return page.extract_text() or "[No text detected]"


def extract_tables_single_page(pdf_path, page_number, verbose=False):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_number]
            raw_tables = page.extract_tables(table_settings=DEFAULT_TABLE_SETTINGS)
            valid_tables = [t for t in raw_tables if is_valid_table(t)]
            dfs = [pd.DataFrame(t) for t in valid_tables]
            strategy = "lines" if dfs else "none"
            return dfs, strategy
    except Exception as e:
        if verbose:
            print(f"⚠️ Error extracting tables from page {page_number + 1}: {e}")
        return [], "error"


def extract_total_pages(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def save_debug_image_single_page(pdf_path, page_number, resolution=100, table_settings=None):
    table_settings = table_settings or DEFAULT_TABLE_SETTINGS

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number]
        im = page.to_image(resolution=resolution)
        debug_im = im.debug_tablefinder(table_settings=table_settings)
        debug_im.draw_rects(page.rects, stroke="blue", stroke_width=1)

        img_bytes = BytesIO()
        debug_im.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        return img_bytes
        

# === LLM Summaries ===

def summarize_pdf(text_pages, max_pages=5):
    """
    Generate a high-level summary of the entire PDF.
    Uses only first `max_pages` worth of text to avoid token overflow.
    """
    combined_text = "\n\n".join([text_pages[f"Page {i+1}"] for i in range(min(max_pages, len(text_pages)))])
    
    prompt = f"""You are an assistant that summarizes PDF documents.
Here is the beginning of a PDF. Summarize the purpose, key sections, and what this document is about:

{combined_text}
"""

    response = client.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.4)
    )

    return response.text.strip()


def summarize_page(page_text, context_summary=""):
    """
    Summarize a single page, optionally using a global context from the full document.
    """
    prompt = f"""Here is a general summary of the PDF:
{context_summary}

Now, here is one page of the document:
{page_text}

What are the key insights or notable content from this page? Keep it brief."""

    response = client.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.4)
    )

    return response.text.strip()