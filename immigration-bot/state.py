"""State machine and McLovin demo data for immigration document flow."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class State(str, Enum):
    WAITING_FOR_FORM = "waiting_for_form"
    WAITING_FOR_LICENSE = "waiting_for_license"
    WAITING_FOR_SSN = "waiting_for_ssn"
    FILLING = "filling"
    DONE = "done"


# McLovin demo profile data
MCLOVIN_PROFILE = {
    "last_name": "McLovin",
    "first_name": "McLovin",
    "middle_initial": "",
    "other_last_names": "",
    "address": "892 Momona St",
    "apt_number": "",
    "city": "Honolulu",
    "state": "HI",
    "zip_code": "96820",
    "dob": "06/03/1981",
    "ssn": "987-65-4321",
    "email": "mclovin@hawaii.gov",
    "phone": "808-555-0123",
    "citizenship_status": 1,  # 1 = US Citizen
    "list_b_doc_title": "Driver's License",
    "list_b_issuing_authority": "State of Hawaii",
    "list_b_doc_number": "01234567",
    "list_b_expiration": "06/03/2025",
    "list_c_doc_title": "Social Security Card",
    "list_c_issuing_authority": "SSA",
    "list_c_doc_number": "987-65-4321",
    "list_c_expiration": "N/A",
}


def build_fill_instructions(profile: dict) -> str:
    """Build natural language instructions for Reducto to fill the I-9 form."""
    return f"""Fill this I-9 Employment Eligibility Verification form with the following information:

Section 1 - Employee Information:
- Last Name: {profile['last_name']}
- First Name: {profile['first_name']}
- Middle Initial: {profile['middle_initial'] or 'N/A'}
- Other Last Names Used: {profile['other_last_names'] or 'N/A'}
- Address (Street): {profile['address']}
- Apartment Number: {profile['apt_number'] or 'N/A'}
- City: {profile['city']}
- State: {profile['state']}
- ZIP Code: {profile['zip_code']}
- Date of Birth: {profile['dob']}
- Social Security Number: {profile['ssn']}
- Email Address: {profile['email']}
- Phone Number: {profile['phone']}

Citizenship Status:
- Check box 1 (A citizen of the United States)

Section 2 - Employer Review (List B and C Documents):
List B Document:
- Document Title: {profile['list_b_doc_title']}
- Issuing Authority: {profile['list_b_issuing_authority']}
- Document Number: {profile['list_b_doc_number']}
- Expiration Date: {profile['list_b_expiration']}

List C Document:
- Document Title: {profile['list_c_doc_title']}
- Issuing Authority: {profile['list_c_issuing_authority']}
- Document Number: {profile['list_c_doc_number']}
- Expiration Date: {profile['list_c_expiration']}

Employee Signature Date: Today's date
"""


@dataclass
class Session:
    """Represents a user session with state and stored form data."""
    state: State = State.WAITING_FOR_FORM
    form_bytes: Optional[bytes] = None
    form_filename: Optional[str] = None
    form_type: Optional[str] = None
    filled_pdf_path: Optional[str] = None
    messages: list = field(default_factory=list)


# In-memory session storage
sessions: dict[str, Session] = {}


def get_session(session_id: str) -> Session:
    """Get or create a session."""
    if session_id not in sessions:
        sessions[session_id] = Session()
    return sessions[session_id]


def reset_session(session_id: str) -> Session:
    """Reset a session to initial state."""
    sessions[session_id] = Session()
    return sessions[session_id]
