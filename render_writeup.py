#!/usr/bin/env python3
"""Render writeup.md -> self-contained writeup.html (tables + inline image)
for printing to PDF in a browser."""
import base64, os, re
import markdown

BASE = os.path.dirname(os.path.abspath(__file__))
md_path = os.path.join(BASE, "writeup.md")
html_path = os.path.join(BASE, "writeup.html")

with open(md_path, encoding="utf-8") as f:
    text = f.read()

# Inline the speedup.png as a base64 data URI so the HTML is self-contained.
img_rel = "prog1_mandelbrot_threads/speedup.png"
img_abs = os.path.join(BASE, img_rel)
if os.path.exists(img_abs):
    with open(img_abs, "rb") as im:
        b64 = base64.b64encode(im.read()).decode("ascii")
    text = text.replace(img_rel, f"data:image/png;base64,{b64}")

body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])

html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>CS149 Assignment 1 Writeup</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif;
         max-width: 820px; margin: 2em auto; padding: 0 1em; line-height: 1.5;
         color: #1a1a1a; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: .2em; margin-top: 1.4em; }}
  h2 {{ border-bottom: 1px solid #ccc; padding-bottom: .15em; margin-top: 1.3em; }}
  table {{ border-collapse: collapse; margin: 1em 0; font-size: .92em; }}
  th, td {{ border: 1px solid #bbb; padding: 4px 9px; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #f0f0f0; }}
  code {{ background: #f4f4f4; padding: 1px 4px; border-radius: 3px; }}
  img {{ max-width: 100%; height: auto; }}
  @media print {{ h1 {{ page-break-before: always; }}
                  h1:first-of-type {{ page-break-before: avoid; }} }}
</style></head><body>
{body}
</body></html>"""

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)
print("Wrote", html_path, f"({os.path.getsize(html_path)//1024} KB, image inlined)")
