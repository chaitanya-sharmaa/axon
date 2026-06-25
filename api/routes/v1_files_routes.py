import time
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from fastapi.responses import JSONResponse
import PyPDF2
from services.vector_store import vector_store

log = logging.getLogger(__name__)
router = APIRouter(tags=["openai-files"])

@router.post("/v1/files")
async def upload_file(
    file: UploadFile = File(...),
    purpose: str = "assistants",
    authorization: str | None = Header(None)
) -> JSONResponse:
    """Mock OpenAI file upload endpoint. Embeds text files into local vector store."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")
        
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(400, f"Error reading file: {e}")
        
    text = ""
    if file.filename.lower().endswith(".pdf"):
        try:
            from io import BytesIO
            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            raise HTTPException(400, f"Error parsing PDF: {e}")
    else:
        # Fallback to UTF-8 decoding for txt, md, csv, etc.
        try:
            text = content.decode("utf-8")
        except Exception as e:
            raise HTTPException(400, f"File must be valid UTF-8 text or PDF. Error: {e}")
            
    if not text.strip():
        raise HTTPException(400, "File is empty or could not extract text")
        
    # Generate an OpenAI-style file ID
    file_id = f"file-{uuid.uuid4().hex[:24]}"
    
    # Chunk and embed the file in the background (we do it synchronously here for simplicity)
    vector_store.add_file(file_id, text)
    
    return JSONResponse(content={
        "id": file_id,
        "object": "file",
        "bytes": len(content),
        "created_at": int(time.time()),
        "filename": file.filename,
        "purpose": purpose
    })
