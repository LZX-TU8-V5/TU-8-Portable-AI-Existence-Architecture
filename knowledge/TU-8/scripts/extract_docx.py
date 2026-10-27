import zipfile
import os
import re

docx_path = r"C:\Users\qq366410837\Desktop\论文初稿\基于元序场理论的宇宙射线_膝盖_现象新解释.docx"
output_dir = r"C:\Users\qq366410837\Desktop\论文初稿\extracted"
txt_output = r"C:\Users\qq366410837\Desktop\论文初稿\extracted_content.txt"

os.makedirs(output_dir, exist_ok=True)

with zipfile.ZipFile(docx_path, 'r') as zip_ref:
    zip_ref.extractall(output_dir)

# Read the main document content
doc_xml = os.path.join(output_dir, 'word', 'document.xml')
if os.path.exists(doc_xml):
    with open(doc_xml, 'r', encoding='utf-8') as f:
        content = f.read()
    # Strip XML tags for readable output
    text = re.sub(r'<[^>]+>', ' ', content)
    text = re.sub(r'\s+', ' ', text)
    with open(txt_output, 'w', encoding='utf-8') as f:
        f.write(text[:10000])
    print("Done - saved to extracted_content.txt")
else:
    print("document.xml not found")