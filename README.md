# EnterpriseMind AI

EnterpriseMind AI is a secure multi-company knowledge assistant.

Companies can upload internal documents such as policies, manuals,
reports and onboarding guides. Authorised users can then ask questions,
receive answers based only on their organisation's documents and view
the supporting document citations.

## Current progress

- Python virtual environment created
- FastAPI backend created
- Root endpoint created
- Health endpoint created
- Automated endpoint tests created
- Both backend tests passing

## Planned MVP

- User authentication
- Organisations and memberships
- PDF and DOCX uploads
- Text extraction and chunking
- PostgreSQL and pgvector storage
- Document retrieval
- Evidence-based answers
- Filename and page citations
- Cross-organisation data protection

## Run the backend

```powershell
.venv\Scripts\Activate.ps1
python -m uvicorn backend.app.main:app --reload