"""REST routes for Excel import/export."""

from __future__ import annotations

from typing import Annotated
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import File
from fastapi import UploadFile
from fastapi import status
from fastapi.responses import Response

from app.api.deps import ExcelServiceDep
from app.domain.errors import ValidationError
from app.infrastructure.excel.schema import EXCEL_MAX_BYTES

router = APIRouter(tags=["excel"])

UploadExcel = Annotated[UploadFile, File(description="Excel .xlsx workbook")]


@router.get("/versions/{version_id}/excel")
def export_excel(
    version_id: UUID,
    service: ExcelServiceDep,
) -> Response:
    """Export a system version as an ``.xlsx`` workbook."""
    data = service.export_version(version_id)
    filename = f"version-{version_id}.xlsx"
    return Response(
        content=data,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/versions/{version_id}/excel/preview")
async def preview_excel(
    version_id: UUID,
    service: ExcelServiceDep,
    file: UploadExcel,
) -> dict[str, Any]:
    """Parse and validate an uploaded workbook without writing."""
    _ = version_id  # target checked on commit
    data = await file.read()
    if len(data) > EXCEL_MAX_BYTES:
        raise ValidationError(
            f"Excel file exceeds {EXCEL_MAX_BYTES} bytes",
            code="EXCEL_TOO_LARGE",
            entity="ExcelWorkbook",
        )
    preview = service.preview_import(data)
    return preview.summary()


@router.post(
    "/versions/{version_id}/excel/import",
    status_code=status.HTTP_201_CREATED,
)
async def import_excel(
    version_id: UUID,
    service: ExcelServiceDep,
    file: UploadExcel,
) -> dict[str, Any]:
    """Commit a validated workbook into an empty DRAFT version."""
    data = await file.read()
    if len(data) > EXCEL_MAX_BYTES:
        raise ValidationError(
            f"Excel file exceeds {EXCEL_MAX_BYTES} bytes",
            code="EXCEL_TOO_LARGE",
            entity="ExcelWorkbook",
        )
    return service.commit_import(version_id, data)
