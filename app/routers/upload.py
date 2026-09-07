from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
import uuid

from app.config import INBOX_DIR

router = APIRouter()


@router.post("/files")
async def upload_files(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        original_name = Path(f.filename or "").name
        if Path(original_name).suffix.lower() not in (".xlsx", ".xls"):
            raise HTTPException(status_code=400, detail="Разрешены только файлы .xlsx и .xls")
        uid = uuid.uuid4().hex[:8]
        dest = INBOX_DIR / f"{uid}_{original_name}"
        with open(dest, "wb") as buf:
            shutil.copyfileobj(f.file, buf)
        saved.append({"original": original_name, "saved_as": dest.name, "size": dest.stat().st_size})
    return {"files": saved, "count": len(saved)}


@router.get("/files")
async def list_files():
    files = []
    for f in sorted(INBOX_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "original": "_".join(f.name.split("_")[1:]) if "_" in f.name else f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })
    return {"files": files}


@router.delete("/files/{filename}")
async def delete_file(filename: str):
    path = INBOX_DIR / Path(filename).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    path.unlink()
    return {"deleted": filename}
