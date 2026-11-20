"""
Generates a full Portfolio PDF using Playwright.
"""
import os
import tempfile

from django.conf import settings

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # e.g. on Vercel, where Playwright/Chromium is not installed
    sync_playwright = None


def generate_portfolio_pdf(portfolio):
    base_url = settings.FRONTEND_URL.rstrip("/")
    print_url = f"{base_url}/portfolio/{portfolio.slug}/print"
    
    if sync_playwright is None:
        raise RuntimeError("PDF generation is not available on this server (Playwright is not installed).")

    output_dir = os.path.join(settings.BASE_DIR, "tmp_pdfs")
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError:  # read-only filesystem (serverless): fall back to the temp dir
        output_dir = os.path.join(tempfile.gettempdir(), "tmp_pdfs")
        os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{portfolio.slug}_portfolio.pdf")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(print_url, wait_until="networkidle")
            page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"}
            )
        finally:
            # Yeh line ensure karti hai ke browser hamesha band ho, chahe error aaye ya na aaye
            browser.close()

    return pdf_path