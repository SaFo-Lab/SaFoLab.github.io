#!/usr/bin/env python3
"""
Download PDFs from publications.yml and extract the first figure.
Updates the YAML file with picture paths for publications missing images.

Usage:
  python3 scripts/extract_fig1_yaml.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path
import yaml

import requests
import fitz  # PyMuPDF


ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "_data" / "publications.yml"
IMAGES_DIR = ROOT / "images" / "publications"


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def find_pdf_url(paper: dict) -> str:
    """Find PDF URL from paper links."""
    if 'links' not in paper:
        return None

    for link in paper['links']:
        link_type = link.get('type', '')
        url = link.get('url', '')

        # Handle arXiv links
        if link_type == 'arxiv' and 'arxiv.org' in url:
            if '/abs/' in url:
                return url.replace('/abs/', '/pdf/') + '.pdf'
            return url

        # Handle direct PDF links
        if link_type == 'pdf':
            return url

    return None


def download_file(url: str, dest: Path):
    """Download a file from URL to destination."""
    print(f"    Downloading from: {url}")
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(1024 * 64):
            if chunk:
                f.write(chunk)


def extract_first_image_from_pdf(pdf_path: Path, out_path: Path) -> bool:
    """Extract the first image from a PDF or render the first page."""
    doc = fitz.open(str(pdf_path))

    # Try to extract embedded images first (usually Figure 1)
    for page_num in range(min(3, len(doc))):  # Check first 3 pages
        page = doc[page_num]
        images = page.get_images(full=True)

        # Look for substantial images (skip small logos/icons)
        for img_ref in images:
            xref = img_ref[0]
            img_dict = doc.extract_image(xref)
            img_bytes = img_dict.get('image')

            # Skip very small images (likely logos)
            if len(img_bytes) < 10000:  # 10KB threshold
                continue

            ext = img_dict.get('ext', 'png')
            out_path.parent.mkdir(parents=True, exist_ok=True)

            final_path = out_path.with_suffix('.' + ext)
            with open(final_path, 'wb') as f:
                f.write(img_bytes)

            print(f"    Extracted image: {final_path.name}")
            return True

    # Fallback: render first page as image
    if len(doc) > 0:
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        png_path = out_path.with_suffix('.png')
        pix.save(str(png_path))
        print(f"    Rendered first page: {png_path.name}")
        return True

    return False


def main():
    if not YAML_PATH.exists():
        print(f"Could not find {YAML_PATH}")
        sys.exit(1)

    # Load YAML file
    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse YAML
    publications = yaml.safe_load(content)

    if not publications:
        print("No publications found in YAML")
        sys.exit(1)

    print(f"Found {len(publications)} publications")

    # Process only 2025 publications without pictures
    updated = False
    for i, paper in enumerate(publications):
        year = paper.get('year')
        title = paper.get('title', f'paper-{i}')

        # Only process 2025 papers
        if year != 2025:
            continue

        # Skip if picture already exists
        if paper.get('picture'):
            print(f"[{i+1}] {title} - already has picture")
            continue

        print(f"[{i+1}] Processing: {title}")

        # Find PDF URL
        pdf_url = find_pdf_url(paper)
        if not pdf_url:
            print("  No PDF link found, skipping")
            continue

        # Generate image filename
        slug = slugify(title)
        target_path = IMAGES_DIR / slug

        # Download and extract
        with tempfile.TemporaryDirectory() as td:
            pdf_tmp = Path(td) / "paper.pdf"

            try:
                download_file(pdf_url, pdf_tmp)
            except Exception as e:
                print(f"  Failed to download PDF: {e}")
                continue

            try:
                success = extract_first_image_from_pdf(pdf_tmp, target_path)
                if success:
                    # Find the actual created file
                    for ext in ['.png', '.jpg', '.jpeg']:
                        img_file = target_path.with_suffix(ext)
                        if img_file.exists():
                            # Update paper with picture path
                            paper['picture'] = f"/images/publications/{img_file.name}"
                            updated = True
                            print(f"  ✓ Added picture: {paper['picture']}")
                            break
                else:
                    print("  No image extracted")
            except Exception as e:
                print(f"  Failed to extract image: {e}")

    # Save updated YAML if changes were made
    if updated:
        print("\nSaving updated publications.yml...")
        with open(YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(publications, f, default_flow_style=False,
                     allow_unicode=True, sort_keys=False, width=1000)
        print("Done! Publications updated with images.")
    else:
        print("\nNo updates needed.")


if __name__ == '__main__':
    main()
