"""Use case for generating frontend with V0 API."""
import httpx
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from app.config import settings
from mock_v0 import mock_v0_generation, mock_get_generation_status

logger = logging.getLogger(__name__)


async def generate_frontend_with_v0(
    prompt: str,
    context: Optional[str] = None,
    framework: str = "react",
    style: str = "apple-hig",
    components: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generate frontend code using V0 API.
    
    Args:
        prompt: The main prompt for generation
        context: Additional context
        framework: Target framework
        style: Style preference
        components: Specific components to generate
        
    Returns:
        Dictionary with generation results
        
    Raises:
        RuntimeError: If API key is not configured or API request fails
    """
    # For demo purposes, use mock instead of real V0 API
    logger.info(f"Using mock V0 generation for prompt: {prompt[:100]}...")
    
    try:
        result = await mock_v0_generation(
            prompt=prompt,
            context=context,
            framework=framework,
            style=style,
            components=components
        )
        logger.info(f"Mock V0 generation completed: {result.get('generation_id', 'unknown')}")
        return result
        
    except Exception as e:
        error_msg = f"Mock V0 generation error: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


async def get_generation_status(generation_id: str) -> Dict[str, Any]:
    """
    Get status of V0 generation.
    
    Args:
        generation_id: The generation ID to check
        
    Returns:
        Dictionary with generation status
    """
    logger.info(f"Checking mock generation status: {generation_id}")
    
    try:
        result = await mock_get_generation_status(generation_id)
        return result
        
    except Exception as e:
        logger.error(f"Error checking mock generation status: {str(e)}")
        raise RuntimeError(f"Ошибка проверки статуса: {str(e)}")


async def save_generated_files(files: List[Dict[str, Any]], export_path: str) -> bool:
    """
    Save generated files to specified path.
    
    Args:
        files: List of file dictionaries with path and content
        export_path: Base path to save files
        
    Returns:
        True if successful, False otherwise
    """
    try:
        export_dir = Path(export_path)
        export_dir.mkdir(parents=True, exist_ok=True)
        
        for file_data in files:
            file_path = export_dir / file_data["path"]
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(file_data["content"])
            
            logger.info(f"Файл сохранен: {file_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving files: {str(e)}")
        return False


async def create_integration_script(generation_id: str, project_path: str) -> str:
    """
    Create integration script for generated files.
    
    Args:
        generation_id: V0 generation ID
        project_path: Target project path
        
    Returns:
        Path to created integration script
    """
    script_content = f'''#!/usr/bin/env python3
"""
Интеграционный скрипт для V0 генерации {generation_id}
"""
import os
import shutil
from pathlib import Path

print("[INFO] Интеграция V0 компонентов...")

# Пути
V0_EXPORT = Path("scripts/_temp/v0_export")
FRONTEND = Path("{project_path}")

# 1. Бэкап существующих файлов
if (FRONTEND / "app").exists():
    shutil.move(str(FRONTEND / "app"), str(FRONTEND / "app.backup"))
    print("[OK] Бэкап создан: app.backup")

# 2. Копирование из V0
folders_to_copy = ["app", "components", "styles"]
for folder in folders_to_copy:
    src = V0_EXPORT / folder
    dst = FRONTEND / folder
    
    if src.exists():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print(f"[OK] Скопировано: {folder}")

# 3. Установка зависимостей
print("[INFO] Установка зависимостей...")
os.system(f"cd {FRONTEND} && npm install framer-motion lucide-react @hookform/resolvers zod react-hook-form")

# 4. Копирование tailwind.config.ts
if (V0_EXPORT / "tailwind.config.ts").exists():
    shutil.copy2(V0_EXPORT / "tailwind.config.ts", FRONTEND / "tailwind.config.ts")
    print("[OK] tailwind.config.ts обновлён")

print("\\n[OK] Интеграция завершена!")
print(f"Бэкап: {FRONTEND}/app.backup")
print("Запустите: cd frontend && npm run dev")
'''

    script_path = f"scripts/_temp/integrate_v0_{generation_id}.py"
    
    try:
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        logger.info(f"Интеграционный скрипт создан: {script_path}")
        return script_path
        
    except Exception as e:
        logger.error(f"Error creating integration script: {str(e)}")
        raise