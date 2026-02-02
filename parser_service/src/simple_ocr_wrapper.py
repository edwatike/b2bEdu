"""
Simple OCR wrapper using EasyOCR as fallback for PaddleOCR issues.
Lightweight, reliable for basic table extraction.
"""
import os
import logging
from io import BytesIO
from typing import List, Dict, Any, Optional
try:
    import easyocr
except ImportError:
    easyocr = None

logger = logging.getLogger(__name__)

# Global instance to avoid reloading models

_reader: Optional[Any] = None

def get_ocr_reader() -> Any:
    """Get or create EasyOCR reader."""
    global _reader
    if easyocr is None:
        raise RuntimeError("easyocr is not installed")
    if _reader is None:
        logger.info("Initializing EasyOCR reader...")
        _reader = easyocr.Reader(['ru', 'en'])  # Russian + English
        logger.info("EasyOCR initialized")
    return _reader


def _tesseract_image_ocr(image_bytes: bytes) -> str:
    try:
        import pytesseract
    except Exception:
        return ""
    from PIL import Image
    import numpy as np

    image = Image.open(BytesIO(image_bytes))
    return pytesseract.image_to_string(image, lang="rus+eng") or ""

def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text from image bytes using EasyOCR.
    
    Args:
        image_bytes: Image file content
        
    Returns:
        Extracted text as string
    """
    from PIL import Image
    import numpy as np
    
    if easyocr is None:
        return _tesseract_image_ocr(image_bytes)

    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    reader = get_ocr_reader()

    def _run_easyocr(img: Image.Image, second_pass: bool) -> list:
        try:
            arr = np.array(img)
        except Exception:
            return []
        if second_pass:
            try:
                return reader.readtext(
                    arr,
                    paragraph=False,
                    text_threshold=0.6,
                    low_text=0.3,
                    link_threshold=0.3,
                    mag_ratio=2.0,
                    contrast_ths=0.05,
                    adjust_contrast=0.7,
                )
            except Exception:
                return []
        try:
            return reader.readtext(arr)
        except Exception:
            return []

    results = _run_easyocr(image, second_pass=False)

    if results:
        has_pipe = any("тру" in ((t[1] or "").lower()) for t in results if isinstance(t, (list, tuple)) and len(t) >= 2)
        if not has_pipe:
            try:
                big = image.resize((image.width * 2, image.height * 2))
            except Exception:
                big = None
            if big is not None:
                try:
                    from PIL import ImageEnhance

                    big = ImageEnhance.Contrast(big).enhance(1.6)
                except Exception:
                    pass
                results2 = _run_easyocr(big, second_pass=True)
                if results2:
                    results = list(results) + list(results2)

    items = []
    for (bbox, text, confidence) in results:
        t = (text or "").strip()
        if not t:
            continue
        if confidence is not None and float(confidence) < 0.15:
            continue
        try:
            xs = [float(p[0]) for p in bbox]
            ys = [float(p[1]) for p in bbox]
        except Exception:
            continue
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        y_center = (y_min + y_max) / 2.0
        height = max(1.0, y_max - y_min)
        items.append({"x": x_min, "y": y_center, "h": height, "t": t})

    if not items:
        return ""

    items.sort(key=lambda it: (it["y"], it["x"]))
    avg_h = sum(it["h"] for it in items) / max(1, len(items))
    y_tol = max(10.0, avg_h * 0.6)

    lines = []
    current = []
    current_y = None
    for it in items:
        if current_y is None:
            current_y = it["y"]
            current = [it]
            continue
        if abs(it["y"] - current_y) <= y_tol:
            current.append(it)
        else:
            current.sort(key=lambda x: x["x"])
            line = " ".join(x["t"] for x in current).strip()
            if line:
                lines.append(line)
            current = [it]
            current_y = it["y"]

    if current:
        current.sort(key=lambda x: x["x"])
        line = " ".join(x["t"] for x in current).strip()
        if line:
            lines.append(line)

    seen = set()
    uniq = []
    for ln in lines:
        t = (ln or "").strip()
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return "\n".join(uniq)

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF bytes using EasyOCR (for scanned PDFs).
    
    Args:
        pdf_bytes: PDF file content
        
    Returns:
        Extracted text as string
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ImportError("Install PyMuPDF: pip install pymupdf") from e
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_text = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Render page to image
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img_data = pix.tobytes("png")
        
        # Extract text from page image
        page_text = extract_text_from_image(img_data)
        if page_text.strip():
            all_text.append(f"=== PAGE {page_num + 1} ===")
            all_text.append(page_text)
    
    doc.close()
    return "\n".join(all_text)

def is_digital_pdf(pdf_bytes: bytes) -> bool:
    """
    Check if PDF has text content (digital) vs scanned image-only.
    
    Args:
        pdf_bytes: PDF file content
        
    Returns:
        True if PDF has extractable text, False if scanned
    """
    try:
        import fitz
    except ImportError:
        return False
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            text = page.get_text()
            if text and text.strip():
                doc.close()
                return True
        doc.close()
    except Exception:
        pass
    
    return False

def extract_text_from_digital_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from digital PDF using PyMuPDF.
    
    Args:
        pdf_bytes: PDF file content
        
    Returns:
        Extracted text as string
    """
    try:
        import fitz
    except ImportError as e:
        raise ImportError("Install PyMuPDF: pip install pymupdf") from e
    
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    all_text = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            all_text.append(f"=== PAGE {page_num + 1} ===")
            all_text.append(text.strip())
    
    doc.close()
    return "\n".join(all_text)

def smart_extract_text(filename: str, content: bytes) -> str:
    """
    Smart text extraction based on file type and content.
    
    Args:
        filename: File name
        content: File content as bytes
        
    Returns:
        Extracted text as string
    """
    name = (filename or "").lower()
    
    if name.endswith(".pdf"):
        # Check if digital or scanned
        if is_digital_pdf(content):
            logger.info("Digital PDF detected, using direct text extraction")
            return extract_text_from_digital_pdf(content)
        else:
            logger.info("Scanned PDF detected, using OCR")
            return extract_text_from_pdf(content)
    
    elif name.endswith((".png", ".jpg", ".jpeg")):
        logger.info("Image file detected, using OCR")
        return extract_text_from_image(content)
    
    elif name.endswith((".docx", ".xlsx")):
        # For Office docs, we'll use existing extractors
        logger.info(f"Office document detected: {name}")
        return ""
    
    else:
        # Try as text file
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return ""

# Test function
def test_easyocr():
    """Test EasyOCR installation and basic functionality."""
    try:
        reader = get_ocr_reader()
        logger.info("[OK] EasyOCR initialized successfully")
        return True
    except Exception as e:
        logger.error(f"[ERR] EasyOCR initialization failed: {e}")
        return False

if __name__ == "__main__":
    # Quick test
    test_easyocr()
