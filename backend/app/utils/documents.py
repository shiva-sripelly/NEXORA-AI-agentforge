import re
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from app.ai.rag.chunker import TextPart
def normalize(text:str):return re.sub(r"[ \t]+"," ",re.sub(r"\n{3,}","\n\n",text.replace("\x00",""))).strip()
def extract(data:bytes,suffix:str):
 if suffix in {".txt",".md"}:return [TextPart(normalize(data.decode("utf-8")))]
 reader=PdfReader(BytesIO(data));return [TextPart(normalize(page.extract_text() or ""),i+1) for i,page in enumerate(reader.pages) if normalize(page.extract_text() or "")]
def safe_path(root:str,user_id,document_id,suffix:str):
 base=Path(root).resolve();target=(base/str(user_id)/f"{document_id}{suffix}").resolve()
 if base not in target.parents:raise ValueError("Invalid storage path")
 return target
