"""
File text extraction.

Turns an uploaded campaign file (PDF or image) into plain text that the normal
compliance pipeline can check. Strategy, privacy-first:

  PDF  -> pypdf reads the text layer LOCALLY (pure Python, nothing leaves the
          system). Covers most real marketing PDFs.
  Image, or a scanned PDF with no text layer:
       -> local OCR (Tesseract) if it is installed, otherwise
       -> Gemini vision (the file is sent to the model to read).

The method used is returned so the UI can tell the user how the text was read,
and whether the file left the system.
"""
from __future__ import annotations

import io
import shutil

from app.config import get_settings

settings = get_settings()

# Below this many characters, treat a PDF as "no real text layer" (scanned).
_MIN_PDF_CHARS = 15

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")


def _is_pdf(filename: str, content_type: str | None) -> bool:
    return filename.lower().endswith(".pdf") or (content_type == "application/pdf")


def _is_image(filename: str, content_type: str | None) -> bool:
    return filename.lower().endswith(_IMAGE_EXTS) or (content_type or "").startswith("image/")


def _pdf_text_local(data: bytes) -> str:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_local(data: bytes) -> str:
    import pytesseract
    from PIL import Image
    return pytesseract.image_to_string(Image.open(io.BytesIO(data))).strip()


def _gemini_vision_text(data: bytes, mime_type: str) -> str:
    """Ask Gemini to transcribe the text in a file. Sends the file to the model."""
    from google.genai import types

    from app.services.gemini_matching import _get_client  # reuse the lazy client

    client = _get_client()
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=data, mime_type=mime_type),
            "Transcribe ALL text in this file exactly as written. "
            "Return only the text, no commentary.",
        ],
    )
    return (resp.text or "").strip()


def extract_text(data: bytes, filename: str, content_type: str | None = None) -> dict:
    """
    Returns {text, method, note}. method is one of:
      pdf-text     - read locally from the PDF text layer (private)
      ocr-local    - read locally via Tesseract OCR (private)
      gemini-vision- read by the AI model (file was sent to the model)
      none         - could not extract; user should paste text manually
    """
    is_pdf = _is_pdf(filename, content_type)
    is_image = _is_image(filename, content_type)

    if not is_pdf and not is_image:
        return {"text": "", "method": "none",
                "note": "Unsupported file type. Upload a PDF or an image (PNG/JPG)."}

    # 1. PDF with a real text layer -> local, private.
    if is_pdf:
        try:
            text = _pdf_text_local(data)
        except Exception:  # noqa: BLE001 - corrupt/locked PDF, fall through to vision
            text = ""
        if len(text) >= _MIN_PDF_CHARS:
            return {"text": text, "method": "pdf-text",
                    "note": "Text read locally from the PDF. Nothing was sent to the AI for extraction."}

    # 2. Image -> local OCR if Tesseract is installed, private.
    if is_image and _tesseract_available():
        try:
            text = _ocr_local(data)
            if text:
                return {"text": text, "method": "ocr-local",
                        "note": "Text read locally via OCR. Nothing was sent to the AI for extraction."}
        except Exception:  # noqa: BLE001 - fall through to vision
            pass

    # 3. Fallback: Gemini vision (image, or scanned PDF). File is sent to the model.
    if settings.gemini_enabled:
        mime = "application/pdf" if is_pdf else (content_type or "image/png")
        try:
            text = _gemini_vision_text(data, mime)
            if text:
                return {"text": text, "method": "gemini-vision",
                        "note": "Text read by AI vision. The file was sent to the model for extraction."}
        except Exception as e:  # noqa: BLE001
            return {"text": "", "method": "none",
                    "note": f"Could not read the file with AI vision ({type(e).__name__}). Paste the text manually."}

    return {"text": "", "method": "none",
            "note": ("Could not extract text. The PDF has no text layer and no OCR/AI fallback is available. "
                     "Install Tesseract for local OCR, configure a Gemini key, or paste the text manually.")}
