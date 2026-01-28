#!/usr/bin/env python3
"""
Manually download and extract figures for remaining publications.
"""
import tempfile
from pathlib import Path
import yaml
import requests
import fitz

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "_data" / "publications.yml"
IMAGES_DIR = ROOT / "images" / "publications"

def slugify(text: str) -> str:
    import re
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")

def download_file(url: str, dest: Path):
    print(f"    Downloading from: {url}")
    resp = requests.get(url, stream=True, timeout=30)
    resp.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in resp.iter_content(1024 * 64):
            if chunk:
                f.write(chunk)

def extract_first_image_from_pdf(pdf_path: Path, out_path: Path) -> bool:
    doc = fitz.open(str(pdf_path))

    # Try to extract embedded images first
    for page_num in range(min(3, len(doc))):
        page = doc[page_num]
        images = page.get_images(full=True)

        for img_ref in images:
            xref = img_ref[0]
            img_dict = doc.extract_image(xref)
            img_bytes = img_dict.get('image')

            if len(img_bytes) < 10000:
                continue

            ext = img_dict.get('ext', 'png')
            out_path.parent.mkdir(parents=True, exist_ok=True)

            final_path = out_path.with_suffix('.' + ext)
            with open(final_path, 'wb') as f:
                f.write(img_bytes)

            print(f"    Extracted image: {final_path.name}")
            return True

    # Fallback: render first page
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
    # Manual mapping of papers to PDF URLs
    manual_pdfs = {
        "DataGen: Unified Synthetic Dataset Generation via Large Language Models":
            "https://openreview.net/pdf?id=F5R0lG74Tu",
        "Can Watermarks be Used to Detect LLM IP Infringement For Free?":
            "https://openreview.net/pdf?id=KRMSH1GxUK",
        "PIGuard: Prompt Injection Guardrail via Mitigating Overdefense for Free":
            "https://aclanthology.org/2025.acl-long.1468.pdf",
        "MetaAgent: Automatically Building Multi-Agent System based on Finite State Machine":
            "https://openreview.net/pdf?id=vOxaD3hhPt",
    }

    with open(YAML_PATH, 'r') as f:
        publications = yaml.safe_load(f)

    updated = False
    for pub in publications:
        title = pub.get('title', '')

        if title not in manual_pdfs:
            continue

        if pub.get('picture'):
            print(f"Skipping {title} - already has picture")
            continue

        print(f"Processing: {title}")
        pdf_url = manual_pdfs[title]
        slug = slugify(title)
        target_path = IMAGES_DIR / slug

        with tempfile.TemporaryDirectory() as td:
            pdf_tmp = Path(td) / "paper.pdf"

            try:
                download_file(pdf_url, pdf_tmp)
            except Exception as e:
                print(f"  Failed to download: {e}")
                continue

            try:
                success = extract_first_image_from_pdf(pdf_tmp, target_path)
                if success:
                    for ext in ['.png', '.jpg', '.jpeg']:
                        img_file = target_path.with_suffix(ext)
                        if img_file.exists():
                            pub['picture'] = f"/images/publications/{img_file.name}"
                            updated = True
                            print(f"  ✓ Added picture: {pub['picture']}")
                            break
            except Exception as e:
                print(f"  Failed to extract: {e}")

    if updated:
        print("\nSaving updated publications.yml...")
        with open(YAML_PATH, 'w') as f:
            yaml.dump(publications, f, default_flow_style=False,
                     allow_unicode=True, sort_keys=False, width=1000)
        print("Done!")
    else:
        print("\nNo updates made.")

if __name__ == '__main__':
    main()
