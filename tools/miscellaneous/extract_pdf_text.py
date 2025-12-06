import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception:
    print('pypdf not installed')
    raise

if __name__ == '__main__':
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"d:\Paper\localcode\covid-19.pdf")
    out_path = pdf_path.with_suffix('.txt')
    reader = PdfReader(str(pdf_path))
    texts = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        texts.append(f"--- PAGE {i+1} ---\n")
        texts.append(text if text else '')
    out_path.write_text('\n'.join(texts), encoding='utf-8')
    print(f'Wrote extracted text to {out_path}')
