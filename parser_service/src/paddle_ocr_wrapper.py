"""
PaddleOCR + PP-Structure wrapper for smart document parsing.
Supports PDF, images with table/layout recognition.
"""
import os
import logging
from io import BytesIO
from typing import List, Dict, Any, Optional
try:
    from paddleocr import PPStructureV3
    PPStructure = PPStructureV3  # Alias for compatibility
except ImportError as e:
    raise ImportError("Install paddleocr: pip install paddleocr") from e

logger = logging.getLogger(__name__)

# Global instance to avoid reloading models
_table_engine: Optional[PPStructure] = None

def get_table_engine() -> PPStructure:
    """Get or create PPStructure table engine."""
    global _table_engine
    if _table_engine is None:
        logger.info("Initializing PaddleOCR PP-StructureV3 engine...")
        _table_engine = PPStructureV3()
        logger.info("PaddleOCR PP-StructureV3 initialized")
    return _table_engine

def extract_tables_from_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF bytes using PaddleOCR PP-Structure.
    
    Args:
        pdf_bytes: PDF file content
        
    Returns:
        List of table dictionaries with structure and content
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise ImportError("Install PyMuPDF: pip install pymupdf") from e
    
    # Convert PDF pages to images
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    engine = get_table_engine()
    all_tables = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Render page to image (higher DPI for better OCR)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img_data = pix.tobytes("png")
        
        # Convert to PIL Image
        from PIL import Image
        image = Image.open(BytesIO(img_data))
        
        # Run PP-Structure
        result = engine(image)
        
        # Extract tables from result
        for item in result:
            if item.get('type') == 'table':
                table_data = {
                    'page': page_num + 1,
                    'bbox': item.get('bbox', []),
                    'html': item.get('html', ''),
                    'res': item.get('res', []),
                    'confidence': item.get('confidence', 0.0)
                }
                all_tables.append(table_data)
                logger.info(f"Table found on page {page_num + 1}: {len(table_data.get('res', []))} cells")
    
    doc.close()
    return all_tables

def extract_tables_from_image(image_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract tables from image bytes using PaddleOCR PP-Structure.
    
    Args:
        image_bytes: Image file content
        
    Returns:
        List of table dictionaries with structure and content
    """
    from PIL import Image
    
    image = Image.open(BytesIO(image_bytes))
    engine = get_table_engine()
    result = engine(image)
    
    tables = []
    for item in result:
        if item.get('type') == 'table':
            table_data = {
                'page': 1,
                'bbox': item.get('bbox', []),
                'html': item.get('html', ''),
                'res': item.get('res', []),
                'confidence': item.get('confidence', 0.0)
            }
            tables.append(table_data)
            logger.info(f"Table found in image: {len(table_data.get('res', []))} cells")
    
    return tables

def tables_to_text(tables: List[Dict[str, Any]]) -> str:
    """
    Convert extracted tables to plain text for position parsing.
    
    Args:
        tables: List of table dictionaries
        
    Returns:
        Plain text representation of tables
    """
    lines = []
    for table in tables:
        page = table.get('page', 1)
        lines.append(f"=== TABLE PAGE {page} ===")
        
        # Try to extract structured data from 'res' field
        cells = table.get('res', [])
        if cells:
            # Group cells by row
            rows = {}
            for cell in cells:
                bbox = cell.get('bbox', [])
                text = cell.get('text', '').strip()
                if not text:
                    continue
                    
                # Estimate row by y-coordinate
                y = bbox[1] if len(bbox) > 1 else 0
                if y not in rows:
                    rows[y] = []
                rows[y].append((bbox[0], text))  # (x, text)
            
            # Sort rows by y-coordinate and cells by x-coordinate
            for y in sorted(rows.keys()):
                row_cells = sorted(rows[y], key=lambda x: x[0])
                row_text = " | ".join(text for _, text in row_cells)
                lines.append(row_text)
        
        # Fallback: use HTML if available
        html = table.get('html', '')
        if html and not cells:
            # Simple HTML to text conversion
            import re
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                lines.append(text)
        
        lines.append("")  # Empty line between tables
    
    return "\n".join(lines)

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

# Test function
def test_paddle_ocr():
    """Test PaddleOCR installation and basic functionality."""
    try:
        engine = get_table_engine()
        logger.info("[OK] PaddleOCR PP-Structure initialized successfully")
        return True
    except Exception as e:
        logger.error(f"[ERR] PaddleOCR initialization failed: {e}")
        return False

if __name__ == "__main__":
    # Quick test
    test_paddle_ocr()
