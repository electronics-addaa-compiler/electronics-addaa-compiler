
import os
import tempfile
import subprocess
import secrets
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Electronics Addaa Arduino Compiler")

ACCESS_CODE = os.environ.get("COMPILER_ACCESS_CODE", "")

BOARDS = {
    "uno": "arduino:avr:uno",
    "nano": "arduino:avr:nano",
    "mega": "arduino:avr:mega"
}

class CompileRequest(BaseModel):
    code: str = Field(min_length=1, max_length=150000)
    board: str = "uno"

@app.get("/")
def home():
    return {"status": "online", "service": "Electronics Addaa Compiler"}

@app.post("/compile")
def compile_code(
    request: CompileRequest,
    x_access_code: str = Header(default="")
):
    if not ACCESS_CODE:
        raise HTTPException(503, "Compiler access code not configured")

    if not secrets.compare_digest(x_access_code, ACCESS_CODE):
        raise HTTPException(401, "Invalid access code")

    board = request.board.lower()

    if board not in BOARDS:
        raise HTTPException(400, "Supported boards: uno, nano, mega")

    try:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "sketch"
            folder.mkdir()

            sketch = folder / "sketch.ino"
            sketch.write_text(request.code, encoding="utf-8")

            result = subprocess.run(
                [
                    "arduino-cli",
                    "compile",
                    "--fqbn", BOARDS[board],
                    str(folder)
                ],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                raise HTTPException(
                    400,
                    detail={
                        "error": "Compilation failed",
                        "output": result.stderr[-6000:]
                    }
                )

            firmware = folder / "build" / BOARDS[board] / "sketch.ino.hex"

            if not firmware.exists():
                raise HTTPException(500, "Firmware file not generated")

            return {
                "success": True,
                "board": board,
                "filename": "sketch.ino.hex",
                "hex": firmware.read_text(encoding="utf-8"),
                "message": "Compilation successful"
            }

    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Compilation timed out")
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(500, str(error))
  
