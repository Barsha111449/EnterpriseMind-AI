import io
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_current_user
from backend.app.core.permissions import (
    DOCUMENT_UPLOAD_ROLES,
    KNOWLEDGE_ACCESS_ROLES,
    require_roles,
)
from backend.app.database.session import get_db
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.schemas.authentication import CurrentUserResponse
from backend.app.schemas.document import (
    DocumentChunkResponse,
    DocumentProcessingResponse,
    DocumentResponse,
)
from backend.app.services.document_processing import (
    extract_document_chunks,
)
from backend.app.services.embedding_service import (
    generate_embeddings,
)


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
)

UPLOAD_ROOT = Path("storage") / "uploads"

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

ALLOWED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
}


def validate_file_content(
    extension: str,
    content: bytes,
) -> None:
    """Check that uploaded content matches its file extension."""

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is not a valid PDF.",
            )

    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                archive_files = set(archive.namelist())

                required_files = {
                    "[Content_Types].xml",
                    "word/document.xml",
                }

                if not required_files.issubset(archive_files):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The uploaded file is not a valid DOCX.",
                    )

        except zipfile.BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is not a valid DOCX.",
            ) from exc


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> DocumentResponse:
    """Upload one PDF or DOCX document."""

    require_roles(
        current_user,
        DOCUMENT_UPLOAD_ROLES,
        detail="Document upload access required.",
    )

    original_filename = Path(file.filename or "").name

    if not original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file must have a filename.",
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and DOCX files are allowed.",
        )

    content = await file.read(MAX_FILE_SIZE_BYTES + 1)
    await file.close()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The maximum allowed file size is 10 MB.",
        )

    validate_file_content(extension, content)

    document_id = uuid.uuid4()

    organization_directory = (
        UPLOAD_ROOT / str(current_user.organization_id)
    )

    organization_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        organization_directory / f"{document_id}{extension}"
    )

    document = Document(
        id=document_id,
        organization_id=current_user.organization_id,
        uploaded_by_user_id=current_user.user_id,
        original_filename=original_filename,
        storage_path=destination.as_posix(),
        content_type=ALLOWED_FILE_TYPES[extension],
        file_size_bytes=len(content),
        status="uploaded",
    )

    try:
        destination.write_bytes(content)

        database_session.add(document)
        database_session.commit()
        database_session.refresh(document)

    except Exception:
        database_session.rollback()
        destination.unlink(missing_ok=True)
        raise

    return DocumentResponse.model_validate(document)


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[DocumentResponse]:
    """List documents belonging to the current organisation."""

    require_roles(
        current_user,
        KNOWLEDGE_ACCESS_ROLES,
        detail="Document access required.",
    )

    statement = (
        select(Document)
        .where(
            Document.organization_id
            == current_user.organization_id
        )
        .order_by(Document.created_at.desc())
    )

    documents = database_session.scalars(statement).all()

    return [
        DocumentResponse.model_validate(document)
        for document in documents
    ]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document(
    document_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> DocumentResponse:
    """Return one document belonging to the current organisation."""

    require_roles(
        current_user,
        KNOWLEDGE_ACCESS_ROLES,
        detail="Document access required.",
    )

    statement = select(Document).where(
        Document.id == document_id,
        Document.organization_id
        == current_user.organization_id,
    )

    document = database_session.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return DocumentResponse.model_validate(document)


@router.get(
    "/{document_id}/download",
    response_class=FileResponse,
)
def download_document(
    document_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> FileResponse:
    """Download one document belonging to the current organisation."""

    require_roles(
        current_user,
        KNOWLEDGE_ACCESS_ROLES,
        detail="Document access required.",
    )

    statement = select(Document).where(
        Document.id == document_id,
        Document.organization_id
        == current_user.organization_id,
    )

    document = database_session.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    organization_directory = (
        UPLOAD_ROOT / str(current_user.organization_id)
    ).resolve()

    file_path = Path(document.storage_path).resolve()

    try:
        file_path.relative_to(organization_directory)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        ) from exc

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        )

    return FileResponse(
        path=file_path,
        media_type=document.content_type,
        filename=document.original_filename,
    )


@router.post(
    "/{document_id}/process",
    response_model=DocumentProcessingResponse,
)
def process_document(
    document_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> DocumentProcessingResponse:
    """Extract text, create chunks, generate embeddings, and store them."""

    require_roles(
        current_user,
        DOCUMENT_UPLOAD_ROLES,
        detail="Document processing access required.",
    )

    statement = select(Document).where(
        Document.id == document_id,
        Document.organization_id
        == current_user.organization_id,
    )

    document = database_session.scalar(statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    organization_directory = (
        UPLOAD_ROOT / str(current_user.organization_id)
    ).resolve()

    file_path = Path(document.storage_path).resolve()

    try:
        file_path.relative_to(organization_directory)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        ) from exc

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        )

    document.status = "processing"
    document.error_message = None
    database_session.commit()

    try:
        extracted_chunks = extract_document_chunks(
            file_path
        )

        if not extracted_chunks:
            raise ValueError(
                "No extractable text was found in the document."
            )

        chunk_texts = [
            extracted_chunk.content
            for extracted_chunk in extracted_chunks
        ]

        embeddings = generate_embeddings(chunk_texts)

        if len(embeddings) != len(extracted_chunks):
            raise ValueError(
                "The number of embeddings does not match "
                "the number of document chunks."
            )

        database_session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.organization_id
                == current_user.organization_id,
            )
        )

        for chunk_index, extracted_chunk in enumerate(
            extracted_chunks
        ):
            database_session.add(
                DocumentChunk(
                    organization_id=(
                        current_user.organization_id
                    ),
                    document_id=document.id,
                    chunk_index=chunk_index,
                    page_number=(
                        extracted_chunk.page_number
                    ),
                    content=extracted_chunk.content,
                    character_count=len(
                        extracted_chunk.content
                    ),
                    embedding=embeddings[chunk_index],
                )
            )

        document.status = "ready"
        document.error_message = None

        database_session.commit()

        return DocumentProcessingResponse(
            document_id=document.id,
            status=document.status,
            chunk_count=len(extracted_chunks),
        )

    except Exception as exc:
        database_session.rollback()

        failed_document = database_session.scalar(
            statement
        )

        if failed_document is not None:
            failed_document.status = "failed"
            failed_document.error_message = str(exc)[:2000]

            database_session.commit()

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document processing failed.",
        ) from exc


@router.get(
    "/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
)
def list_document_chunks(
    document_id: uuid.UUID,
    current_user: Annotated[
        CurrentUserResponse,
        Depends(get_current_user),
    ],
    database_session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> list[DocumentChunkResponse]:
    """List stored chunks for one organisation document."""

    require_roles(
        current_user,
        KNOWLEDGE_ACCESS_ROLES,
        detail="Document access required.",
    )

    document_statement = select(Document).where(
        Document.id == document_id,
        Document.organization_id
        == current_user.organization_id,
    )

    document = database_session.scalar(document_statement)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    chunks_statement = (
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.organization_id
            == current_user.organization_id,
        )
        .order_by(DocumentChunk.chunk_index)
    )

    chunks = database_session.scalars(
        chunks_statement
    ).all()

    return [
        DocumentChunkResponse.model_validate(chunk)
        for chunk in chunks
    ]