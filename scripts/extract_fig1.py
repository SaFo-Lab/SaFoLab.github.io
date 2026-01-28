#!/usr/bin/env python3
"""
Download PDFs referenced in publications/index.html and extract the first
embedded image (Figure 1) or render the first page if none found.

Saves images into `images/publications/` using the filename currently in the
HTML if present, otherwise uses a slugified title.

Usage:
  pip install -r requirements.txt
  python3 scripts/extract_fig1.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "publications" / "index.html"
IMAGES_DIR = ROOT / "images" / "publications"


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def find_pdf_link(tr):
    # Heuristic: find <a> with href containing 'pdf' or 'arxiv.org/abs' or 'openreview'
    for a in tr.find_all('a', href=True):
        href = a['href']
        if 'pdf' in href or 'arxiv.org/abs' in href or 'openreview.net' in href or href.endswith('.pdf'):
            return href
    return None


def normalize_pdf_url(href: str) -> str:
    if href.startswith('http'):
        if 'arxiv.org/abs' in href:
            # convert abs to pdf
            return href.replace('arxiv.org/abs', 'arxiv.org/pdf') + '.pdf' if not href.endswith('.pdf') else href
        return href
    # relative links
    return 'https://xiaocw11.github.io' + href


def download_file(url: str, dest: Path):
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(1024 * 64):
            if chunk:
                f.write(chunk)


def extract_first_image_from_pdf(pdf_path: Path, out_path: Path) -> bool:
    doc = fitz.open(str(pdf_path))
    # try to extract embedded images first
    for page in doc:
        images = page.get_images(full=True)
        if images:
            xref = images[0][0]
            img_dict = doc.extract_image(xref)
            img_bytes = img_dict.get('image')
            ext = img_dict.get('ext', 'png')
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path.with_suffix('.' + ext), 'wb') as f:
                f.write(img_bytes)
            return True
    # fallback: render first page
    if len(doc) > 0:
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        png_path = out_path.with_suffix('.png')
        pix.save(str(png_path))
        return True
    return False


def main():
    if not HTML_PATH.exists():
        print(f"Could not find {HTML_PATH}")
        sys.exit(1)

    soup = BeautifulSoup(HTML_PATH.read_text(encoding='utf-8'), 'html.parser')
    rows = soup.find_all('tr', class_='publication')
    print(f"Found {len(rows)} publications in {HTML_PATH}")

    for i, tr in enumerate(rows, 1):
        title_tag = tr.find('b')
        title = title_tag.get_text(strip=True) if title_tag else f'pub-{i}'
        pdf_href = find_pdf_link(tr)

        # determine target image path from existing img tag if any
        img_tag = tr.find('img')
        if img_tag and img_tag.get('src'):
            src = img_tag['src'].lstrip('/')
            target_path = ROOT / src
        else:
            slug = slugify(title)
            target_path = IMAGES_DIR / f"{slug}.png"

        print(f"[{i}/{len(rows)}] {title}")
        if not pdf_href:
            print("  no pdf link found, skipping")
            continue

        pdf_url = normalize_pdf_url(pdf_href)
        print(f"  pdf: {pdf_url}")

        with tempfile.TemporaryDirectory() as td:
            pdf_tmp = Path(td) / "paper.pdf"
            try:
                download_file(pdf_url, pdf_tmp)
            except Exception as e:
                print(f"  failed to download PDF: {e}")
                continue

            try:
                ok = extract_first_image_from_pdf(pdf_tmp, target_path.with_suffix(''))
                if ok:
                    print(f"  saved figure (check images/publications) ")
                else:
                    print("  no image extracted")
            except Exception as e:
                print(f"  failed to extract image: {e}")


if __name__ == '__main__':
    main()
