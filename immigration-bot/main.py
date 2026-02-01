"""FastAPI backend for immigration document assistant."""

import os
import logging
import uuid
import urllib.parse
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from immigration_strategy import RecommendationEngine

from state import (State, Session, get_session, reset_session, MCLOVIN_PROFILE,
                   build_fill_instructions, extract_investigation_profile)
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

# Strategy engine (loaded once at startup)
strategy_engine = RecommendationEngine()
STRATEGY_CACHE = Path(__file__).parent / "immigration_strategy" / "h1b_graph.pkl"


@app.on_event("startup")
async def startup():
    ping_db()
    try:
        strategy_engine.load_from_cache(str(STRATEGY_CACHE))
        logger.info("Strategy engine loaded (%d cases)", len(strategy_engine.builder.cases))
    except Exception as e:
        logger.warning("Strategy engine not available: %s", e)


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
    ready_to_investigate: bool = False


@app.get("/")
async def index():
    """Serve the frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Handle chat messages."""
    session = get_session(req.session_id)
    msg_lower = req.message.lower().strip()

    # ── "Send to candidate" intent ──
    send_patterns = [
        "send it to", "send to candidate", "send to the candidate",
        "cool send", "send report", "email the candidate", "send the report",
    ]
    is_send = any(p in msg_lower for p in send_patterns)

    if is_send and session.investigation_result:
        candidate_email = MCLOVIN_PROFILE.get("email", "mclovin@hawaii.gov")
        candidate_name = MCLOVIN_PROFILE.get("first_name", "McLovin")
        return ChatResponse(
            response=(
                f"Done! The strategy report has been sent to "
                f"**{candidate_name}** at **{candidate_email}**.\n\n"
                f"The email includes the full analysis with strategy "
                f"recommendations based on our review of 61 H-1B AAO appeal "
                f"cases. They'll receive it shortly!"
            ),
            state=session.state.value,
        )

    # ── Additional context during PROFILE_UPLOADED ──
    if session.state == State.PROFILE_UPLOADED:
        session.additional_context = req.message
        if session.investigation_profile:
            session.investigation_profile["additional_context"] = req.message
        return ChatResponse(
            response=(
                "Got it, I've noted that additional context. Hit the "
                "**Investigate** button whenever you're ready to run the analysis!"
            ),
            state=session.state.value,
        )

    # ── Default chat ──
    context = f"Current state: {session.state.value}"
    if session.form_type:
        context += f"\nUser uploaded form: {session.form_type}"

    response = chat(req.message, context)
    return ChatResponse(response=response, state=session.state.value)


DEMO_RFE_TEXT = (
    "USCIS Request for Evidence (RFE)\n"
    "Receipt Number: WAC-25-123-45678\n"
    "Beneficiary: McLovin\n"
    "Petitioner: Pumpkin Tech Consulting LLC\n"
    "Classification: H-1B Specialty Occupation\n"
    "Issue: Specialty Occupation\n"
    "Wage Level: Level I ($73,000/year)\n"
    "Service Center: California Service Center"
)

DEMO_PROFILE_TEXT = (
    "Candidate Profile\n"
    "Name: McLovin\n"
    "Email: mclovin@hawaii.gov\n"
    "Current Position: Software Developer\n"
    "Company: Pumpkin Tech Consulting LLC\n"
    "Company Type: Consulting\n"
    "Wage Level: Level I\n"
    "Education: B.S. Computer Science\n"
    "RFE Issues: Specialty Occupation\n"
    "Current Arguments: O*NET Citation"
)


def _classify_upload(filename: str, parsed_text: str) -> str:
    """Classify an uploaded document as 'rfe', 'profile', or 'form'."""
    fn_lower = filename.lower()
    text_lower = parsed_text.lower()

    if "rfe" in fn_lower or "request for evidence" in text_lower or "rfe" in text_lower:
        return "rfe"
    if "profile" in fn_lower or "candidate profile" in text_lower:
        return "profile"
    return "form"


def _is_demo_doc(filename: str) -> Optional[str]:
    """Return 'rfe' or 'profile' if the filename matches a demo sample doc."""
    fn = filename.lower()
    if "mclovin_rfe" in fn or fn == "mclovin_rfe.pdf":
        return "rfe"
    if "mclovin_profile" in fn or fn == "mclovin_profile.pdf":
        return "profile"
    return None


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
        # ── Demo bypass: skip API calls for known sample docs ──
        demo_type = _is_demo_doc(filename)
        if demo_type:
            if demo_type == "rfe":
                session.rfe_text = DEMO_RFE_TEXT
                session.state = State.RFE_UPLOADED
                logger.info("Demo RFE loaded (bypassed API)")
                return UploadResponse(
                    response=(
                        "Got it! I've received the **Request for Evidence (RFE)** "
                        "for case WAC-25-123-45678.\n\n"
                        "Now upload the **Candidate Profile** so I can cross-reference "
                        "both documents for the analysis."
                    ),
                    state=session.state.value,
                )
            else:  # profile
                session.profile_text = DEMO_PROFILE_TEXT
                if session.state == State.RFE_UPLOADED:
                    session.state = State.PROFILE_UPLOADED
                    session.investigation_profile = extract_investigation_profile(
                        session.rfe_text or "", session.profile_text
                    )
                    logger.info("Demo profile loaded, ready to investigate")
                    return UploadResponse(
                        response=(
                            "Got the **Candidate Profile** for McLovin!\n\n"
                            "I now have both documents. Type any additional context "
                            "in the chat, or hit the **Investigate** button to start "
                            "the analysis."
                        ),
                        state=session.state.value,
                        ready_to_investigate=True,
                    )
                else:
                    session.state = State.RFE_UPLOADED
                    logger.info("Demo profile loaded first, waiting for RFE")
                    return UploadResponse(
                        response=(
                            "Got the **Candidate Profile**!\n\n"
                            "Now upload the **RFE document** so I can analyze it."
                        ),
                        state=session.state.value,
                    )

        # ── Try to classify via API for non-demo docs ──
        parsed_text = parse_form(file_bytes, filename)
        form_type = identify_form(parsed_text)
        doc_class = _classify_upload(filename, parsed_text)

        # ── RFE investigation flow ──
        if doc_class == "rfe":
            session.rfe_text = parsed_text
            session.state = State.RFE_UPLOADED
            return UploadResponse(
                response=(
                    f"Got it! I've received the **Request for Evidence (RFE)** "
                    f"({form_type}).\n\n"
                    "Now upload the **Candidate Profile** so I can cross-reference "
                    "both documents for the analysis."
                ),
                state=session.state.value,
            )

        if doc_class == "profile":
            session.profile_text = parsed_text
            if session.state == State.RFE_UPLOADED:
                session.state = State.PROFILE_UPLOADED
                session.investigation_profile = extract_investigation_profile(
                    session.rfe_text or "", session.profile_text
                )
                return UploadResponse(
                    response=(
                        "Got the **Candidate Profile** too!\n\n"
                        "I now have both documents. Type any additional context "
                        "in the chat, or hit the **Investigate** button to start "
                        "the analysis."
                    ),
                    state=session.state.value,
                    ready_to_investigate=True,
                )
            else:
                session.state = State.RFE_UPLOADED
                return UploadResponse(
                    response=(
                        "Got the **Candidate Profile**!\n\n"
                        "Now upload the **RFE document** so I can analyze it."
                    ),
                    state=session.state.value,
                )

        # ── Existing I-9 flow (unchanged) ──
        if session.state == State.WAITING_FOR_FORM:
            session.form_bytes = file_bytes
            session.form_filename = filename
            session.form_type = form_type
            session.state = State.WAITING_FOR_LICENSE

            response = (
                f"This looks like a **{form_type}**!\n\n"
                "To fill this out, I'll need:\n"
                "Your Driver's License\n"
                "Your Social Security Card\n\n"
                "Upload your Driver's License when ready!"
            )
            return UploadResponse(response=response, state=session.state.value)

        elif session.state == State.WAITING_FOR_LICENSE:
            session.state = State.WAITING_FOR_SSN
            response = (
                "Got your Driver's License!\n\n"
                "Now upload your Social Security Card and I'll fill out your form."
            )
            return UploadResponse(response=response, state=session.state.value)

        elif session.state == State.WAITING_FOR_SSN:
            session.state = State.FILLING
            if not session.form_bytes:
                raise HTTPException(status_code=400, detail="No form stored in session")
            fill_instructions = build_fill_instructions(MCLOVIN_PROFILE)
            filled_url = fill_form(session.form_bytes, session.form_filename, fill_instructions)
            filled_filename = f"filled_{uuid.uuid4().hex[:8]}.pdf"
            filled_path = DOWNLOADS_DIR / filled_filename
            download_filled_pdf(filled_url, filled_path)
            session.filled_pdf_path = str(filled_path)
            session.state = State.DONE
            response = (
                "Got your Social Security Card!\n\n"
                "**Your I-9 form has been filled!**\n\n"
                "Click below to download your completed form."
            )
            return UploadResponse(
                response=response, state=session.state.value,
                file_url=f"/download/{filled_filename}"
            )

        elif session.state == State.DONE:
            session = reset_session(session_id)
            session.state = State.WAITING_FOR_FORM
            parsed_text = parse_form(file_bytes, filename)
            form_type = identify_form(parsed_text)
            session.form_bytes = file_bytes
            session.form_filename = filename
            session.form_type = form_type
            session.state = State.WAITING_FOR_LICENSE
            response = (
                f"Starting fresh! This looks like a **{form_type}**.\n\n"
                "To fill this out, I'll need:\n"
                "Your Driver's License\n"
                "Your Social Security Card\n\n"
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



# ── Investigation ──

class InvestigateRequest(BaseModel):
    session_id: str = "default"


@app.post("/api/investigate")
async def investigate_endpoint(req: InvestigateRequest):
    """Run H-1B strategy investigation."""
    if not strategy_engine._loaded:
        return {"success": False, "error": "Strategy engine not loaded. Graph cache missing."}

    session = get_session(req.session_id)

    # Use session profile if available (from uploaded docs), else McLovin default
    if session.investigation_profile:
        profile = {k: v for k, v in session.investigation_profile.items()
                   if k != "additional_context"}
    else:
        profile = {
            "job_title": MCLOVIN_PROFILE["job_title"],
            "company_type": MCLOVIN_PROFILE["company_type"],
            "wage_level": MCLOVIN_PROFILE["wage_level"],
            "rfe_issues": MCLOVIN_PROFILE["rfe_issues"],
            "current_arguments": MCLOVIN_PROFILE["current_arguments"],
        }

    try:
        result = strategy_engine.recommend_strategy(profile, top_k=20)
        result.pop("graph_viz_path", None)
        session.investigation_result = result
        session.state = State.RESULTS_READY
        return {
            "success": True,
            "data": result,
            "profile_summary": {
                "job_title": profile.get("job_title", ""),
                "company_type": profile.get("company_type", ""),
                "wage_level": profile.get("wage_level", ""),
                "has_uploaded_docs": session.rfe_text is not None,
            },
        }
    except Exception as e:
        logger.error("Investigation failed: %s", e)
        return {"success": False, "error": str(e)}


@app.post("/api/graph-data")
async def graph_data_endpoint(req: InvestigateRequest):
    """Return lightweight graph node/edge data for SVG visualization."""
    if not strategy_engine._loaded:
        return {"success": False, "error": "Strategy engine not loaded."}

    session = get_session(req.session_id)

    if session.investigation_profile:
        profile = {k: v for k, v in session.investigation_profile.items()
                   if k != "additional_context"}
    else:
        profile = {
            "job_title": MCLOVIN_PROFILE["job_title"],
            "company_type": MCLOVIN_PROFILE["company_type"],
            "wage_level": MCLOVIN_PROFILE["wage_level"],
            "rfe_issues": MCLOVIN_PROFILE["rfe_issues"],
            "current_arguments": MCLOVIN_PROFILE["current_arguments"],
        }

    try:
        data = strategy_engine.get_graph_data(user_profile=profile, top_k_highlight=20)
        return {"success": True, "data": data, "profile": profile}
    except Exception as e:
        logger.error("Graph data error: %s", e)
        return {"success": False, "error": str(e)}


class SendReportRequest(BaseModel):
    email: str
    strategy_index: int = 0
    report_summary: str = ""


@app.post("/api/send-report")
async def send_report_endpoint(req: SendReportRequest):
    """Generate mailto link for investigation report."""
    subject = "H-1B RFE Strategy Report - Pumpkin"
    body = req.report_summary[:2000]
    mailto = f"mailto:{req.email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    return {"status": "ok", "mailto_url": mailto, "message": f"Report ready to send to {req.email}"}


if __name__ == "__main__":
    import uvicorn
    logger.info("🎃 Starting Pumpkin Immigration Assistant...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
