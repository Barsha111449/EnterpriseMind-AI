import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    uploaded_by_user_id: uuid.UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    status: str
    error_message: str | None
    created_at: datetime

class DocumentProcessingResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    chunk_count: int