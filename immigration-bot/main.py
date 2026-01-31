"""FastAPI backend for immigration document assistant."""

import os
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from state import State, Session, get_session, reset_session, MCLOVIN_PROFILE, build_fill_instructions
from services import parse_form, identify_form, fill_form, download_filled_pdf, chat
from db import ping_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pumpkin 🎃 - Immigration Assistant")

# Directory for filled PDFs
DOWNLOADS_DIR = Path(__file__).parent / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Mount frontend static files
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.on_event("startup")
async def startup():
    ping_db()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    state: str


class UploadResponse(BaseModel):
    response: str
    state: str
    file_url: str = None


@app.get("/")
async def index():
    """Serve the frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Handle chat messages."""
    session = get_session(req.session_id)
    
    # Build context based on state
    context = f"Current state: {session.state.value}"
    if session.form_type:
        context += f"\nUser uploaded form: {session.form_type}"
    
    response = chat(req.message, context)
    
    return ChatResponse(response=response, state=session.state.value)


@app.post("/upload", response_model=UploadResponse)
async def upload_endpoint(
    file: UploadFile = File(...),
    session_id: str = Form("default")
):
    """Handle file uploads with state-dependent logic."""
    session = get_session(session_id)
    file_bytes = await file.read()
    filename = file.filename or "document.pdf"
    
    logger.info("Upload received: %s (%d bytes), state: %s", 
                filename, len(file_bytes), session.state.value)
    
    try:
        if session.state == State.WAITING_FOR_FORM:
            # Parse the form to identify it
            parsed_text = parse_form(file_bytes, filename)
            form_type = identify_form(parsed_text)
            
            # Store form for later filling
            session.form_bytes = file_bytes
            session.form_filename = filename
            session.form_type = form_type
            session.state = State.WAITING_FOR_LICENSE
            
            response = (
                f"📋 This looks like a **{form_type}**!\n\n"
                "To fill this out, I'll need:\n"
                "📄 Your Driver's License\n"
                "📄 Your Social Security Card\n\n"
                "Upload your Driver's License when ready!"
            )
            
            return UploadResponse(response=response, state=session.state.value)
        
        elif session.state == State.WAITING_FOR_LICENSE:
            # Don't parse - just acknowledge
            session.state = State.WAITING_FOR_SSN
            
            response = (
                "✅ Got your Driver's License!\n\n"
                "Now upload your Social Security Card and I'll fill out your form."
            )
            
            return UploadResponse(response=response, state=session.state.value)
        
        elif session.state == State.WAITING_FOR_SSN:
            # Don't parse - fill the form with McLovin data
            session.state = State.FILLING
            
            if not session.form_bytes:
                raise HTTPException(status_code=400, detail="No form stored in session")
            
            # Build fill instructions from McLovin profile
            fill_instructions = build_fill_instructions(MCLOVIN_PROFILE)
            
            # Fill the form
            filled_url = fill_form(
                session.form_bytes,
                session.form_filename,
                fill_instructions
            )
            
            # Download and save locally
            filled_filename = f"filled_{uuid.uuid4().hex[:8]}.pdf"
            filled_path = DOWNLOADS_DIR / filled_filename
            download_filled_pdf(filled_url, filled_path)
            
            session.filled_pdf_path = str(filled_path)
            session.state = State.DONE
            
            response = (
                "✅ Got your Social Security Card!\n\n"
                "🎉 **Your I-9 form has been filled!**\n\n"
                "Click below to download your completed form."
            )
            
            return UploadResponse(
                response=response, 
                state=session.state.value,
                file_url=f"/download/{filled_filename}"
            )
        
        elif session.state == State.DONE:
            # Reset and start over
            session = reset_session(session_id)
            session.state = State.WAITING_FOR_FORM
            
            # Process as new form
            parsed_text = parse_form(file_bytes, filename)
            form_type = identify_form(parsed_text)
            
            session.form_bytes = file_bytes
            session.form_filename = filename
            session.form_type = form_type
            session.state = State.WAITING_FOR_LICENSE
            
            response = (
                f"📋 Starting fresh! This looks like a **{form_type}**.\n\n"
                "To fill this out, I'll need:\n"
                "📄 Your Driver's License\n"
                "📄 Your Social Security Card\n\n"
                "Upload your Driver's License when ready!"
            )
            
            return UploadResponse(response=response, state=session.state.value)
        
        else:
            return UploadResponse(
                response="I'm not sure what to do with this file right now.",
                state=session.state.value
            )
            
    except Exception as e:
        logger.error("Upload processing error: %s", e)
        return UploadResponse(
            response=f"Sorry, I had trouble processing that file: {str(e)}",
            state=session.state.value
        )


@app.get("/download/{filename}")
async def download_file(filename: str):
    """Serve filled PDFs for download."""
    file_path = DOWNLOADS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=filename
    )


@app.post("/reset")
async def reset_endpoint(session_id: str = Form("default")):
    """Reset a session."""
    reset_session(session_id)
    return {"status": "reset", "state": State.WAITING_FOR_FORM.value}


if __name__ == "__main__":
    import uvicorn
    logger.info("🎃 Starting Pumpkin Immigration Assistant...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
