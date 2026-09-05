from app.ai.rag.chunker import TextPart,chunk_parts
from app.utils.documents import extract,normalize
def test_txt_extraction_normalization_and_overlap():
 parts=extract(b"AgentForge uses FastAPI.\n\n\nPostgreSQL stores data.",".txt")
 assert "FastAPI" in parts[0].text and "\n\n\n" not in parts[0].text
 chunks=chunk_parts([TextPart("A"*900)],800,120)
 assert len(chunks)==2 and len(chunks[0][0])==800
def test_normalize_removes_nulls():assert normalize("a\x00   b")=="a b"
