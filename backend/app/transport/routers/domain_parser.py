"""Domain Parser API router."""
import asyncio
import logging
import uuid
import json
from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.db.session import get_db
from app.transport.schemas.domain_parser import (
    DomainParserRequestDTO,
    DomainParserBatchResponseDTO,
    DomainParserStatusResponseDTO
)
from app.usecases import get_parsing_run

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for parser runs status
_parser_runs: Dict[str, Dict] = {}


@router.post("/extract-batch", response_model=DomainParserBatchResponseDTO)
async def start_domain_parser_batch(
    request: DomainParserRequestDTO,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start batch domain parsing for INN and email extraction."""
    run_id = request.runId
    domains = request.domains
    
    logger.info(f"=== DOMAIN PARSER BATCH START ===")
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Domains: {len(domains)}")
    
    try:
        # Verify parsing run exists
        parsing_run = await get_parsing_run.execute(db=db, run_id=run_id)
        if not parsing_run:
            raise HTTPException(status_code=404, detail="Parsing run not found")
        
        # Generate unique parser run ID
        parser_run_id = f"parser_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Initialize status
        _parser_runs[parser_run_id] = {
            "runId": run_id,
            "parserRunId": parser_run_id,
            "status": "running",
            "processed": 0,
            "total": len(domains),
            "results": [],
            "startedAt": datetime.now().isoformat(),
        }
        
        # Start background task
        background_tasks.add_task(_process_domain_parser_batch, parser_run_id, run_id, domains)
        
        logger.info(f"Domain parser batch started: {parser_run_id}")
        
        return DomainParserBatchResponseDTO(
            runId=run_id,
            parserRunId=parser_run_id
        )
        
    except Exception as e:
        logger.error(f"Error starting domain parser batch: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/status/{parserRunId}", response_model=DomainParserStatusResponseDTO)
async def get_domain_parser_status(parserRunId: str):
    """Get status of domain parser run."""
    if parserRunId not in _parser_runs:
        raise HTTPException(status_code=404, detail="Parser run not found")
    
    run_data = _parser_runs[parserRunId]
    
    return DomainParserStatusResponseDTO(
        runId=run_data["runId"],
        parserRunId=run_data["parserRunId"],
        status=run_data["status"],
        processed=run_data["processed"],
        total=run_data["total"],
        results=run_data["results"]
    )


async def _process_domain_parser_batch(parser_run_id: str, run_id: str, domains: List[str]):
    """Background task to process domain parser batch."""
    logger.info(f"=== PROCESSING DOMAIN PARSER BATCH ===")
    logger.info(f"Parser Run ID: {parser_run_id}")
    logger.info(f"Domains: {len(domains)}")
    
    results = []
    
    try:
        for i, domain in enumerate(domains):
            logger.info(f"Processing domain {i+1}/{len(domains)}: {domain}")
            
            try:
                result = await _run_domain_parser_for_domain(domain)
                results.append(result)
                
                # Update status
                _parser_runs[parser_run_id]["processed"] = i + 1
                _parser_runs[parser_run_id]["results"] = results
                
                logger.info(f"Domain {domain} processed: INN={result.get('inn')}, Emails={result.get('emails')}")
                
            except Exception as e:
                logger.error(f"Error processing domain {domain}: {e}")
                results.append({
                    "domain": domain,
                    "inn": None,
                    "emails": [],
                    "sourceUrls": [],
                    "error": str(e)
                })
                _parser_runs[parser_run_id]["processed"] = i + 1
                _parser_runs[parser_run_id]["results"] = results
        
        # Mark as completed
        _parser_runs[parser_run_id]["status"] = "completed"
        _parser_runs[parser_run_id]["finishedAt"] = datetime.now().isoformat()
        
        # Save results to database
        await _save_parser_results_to_db(run_id, parser_run_id, results)
        
        logger.info(f"Domain parser batch completed: {parser_run_id}")
        
        # AUTO-TRIGGER COMET: Find domains where parser failed to find INN or Email
        failed_domains = []
        for result in results:
            has_inn = result.get("inn")
            has_email = result.get("emails") and len(result.get("emails", [])) > 0
            
            # If parser didn't find INN or Email, add to failed list
            if not has_inn or not has_email:
                failed_domains.append(result["domain"])
        
        if failed_domains:
            logger.info(f"[AUTO] AUTO-TRIGGER: {len(failed_domains)} domains failed in parser, starting Comet automatically...")
            
            # Import comet router to trigger extraction
            from . import comet
            try:
                # Start Comet extraction for failed domains
                comet_response = await comet._start_comet_batch_internal(run_id, failed_domains, auto_learn=True)
                logger.info(f"[OK] AUTO-TRIGGER: Comet started with run_id={comet_response['cometRunId']}")
                
                # Store comet_run_id in parser run for reference
                _parser_runs[parser_run_id]["auto_comet_run_id"] = comet_response["cometRunId"]
            except Exception as comet_error:
                logger.error(f"[ERR] AUTO-TRIGGER: Failed to start Comet: {comet_error}")
        else:
            logger.info(f"[OK] All domains processed successfully by parser, no need for Comet")
        
    except Exception as e:
        logger.error(f"Error in domain parser batch: {e}")
        _parser_runs[parser_run_id]["status"] = "failed"
        _parser_runs[parser_run_id]["error"] = str(e)


async def _run_domain_parser_for_domain(domain: str) -> Dict:
    """Run domain parser for a single domain."""
    import os
    
    # Path to domain_info_parser
    parser_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "domain_info_parser")
    parser_script = os.path.join(parser_dir, "parser.py")
    
    if not os.path.exists(parser_script):
        raise Exception(f"Domain parser script not found: {parser_script}")
    
    # Use system Python (not venv) because Playwright is installed globally
    # Backend venv doesn't have Playwright
    python_exe = "python"  # Use system Python
    
    logger.info(f"Running domain parser for: {domain}")
    logger.info(f"Python: {python_exe} (system)")
    logger.info(f"Script: {parser_script}")
    
    try:
        # Create a temporary Python script to run the parser
        import tempfile
        script_content = f"""
import sys
import asyncio
import json

# Add parser directory to path
sys.path.insert(0, r'{parser_dir}')

async def main():
    try:
        from parser import DomainInfoParser
        
        parser = DomainInfoParser(headless=True, timeout=15000)
        await parser.start()
        try:
            result = await parser.parse_domain('{domain}')
            print('RESULT_START')
            print(json.dumps(result, ensure_ascii=False))
            print('RESULT_END')
        finally:
            await parser.close()
    except Exception as e:
        print('RESULT_START')
        print(json.dumps({{"domain": "{domain}", "inn": None, "emails": [], "source_urls": [], "error": str(e)}}))
        print('RESULT_END')
        raise

if __name__ == "__main__":
    asyncio.run(main())
"""
        
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            temp_script = f.name
        
        try:
            # Run parser as subprocess using the temp script
            process = await asyncio.create_subprocess_exec(
                python_exe,
                temp_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=parser_dir
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)
            except asyncio.TimeoutError:
                process.kill()
                raise Exception("Domain parser timeout (120s)")
            
            # Decode output
            try:
                stdout_text = stdout.decode('utf-8')
            except UnicodeDecodeError:
                stdout_text = stdout.decode('cp1251', errors='ignore')
            
            try:
                stderr_text = stderr.decode('utf-8')
            except UnicodeDecodeError:
                stderr_text = stderr.decode('cp1251', errors='ignore')
            
            logger.info(f"Domain parser for {domain}:")
            logger.info(f"  - stdout length: {len(stdout_text)}")
            logger.info(f"  - stderr length: {len(stderr_text)}")
            
            if stderr_text:
                logger.warning(f"Domain parser stderr for {domain}:")
                logger.warning(stderr_text)
            
            # Extract result from output
            if 'RESULT_START' in stdout_text and 'RESULT_END' in stdout_text:
                result_start = stdout_text.index('RESULT_START') + len('RESULT_START')
                result_end = stdout_text.index('RESULT_END')
                result_json = stdout_text[result_start:result_end].strip()
                
                logger.info(f"Extracted JSON for {domain}: {result_json[:200]}")
                
                result = json.loads(result_json)
                
                return {
                    "domain": result.get("domain", domain),
                    "inn": result.get("inn"),
                    "emails": result.get("emails", []),
                    "sourceUrls": result.get("source_urls", []),
                    "error": result.get("error")
                }
            else:
                error_msg = f"No result markers found. stdout: {stdout_text[:500]}, stderr: {stderr_text[:500]}"
                logger.error(f"Parser output error for {domain}: {error_msg}")
                raise Exception(error_msg)
        finally:
            # Clean up temp file
            import os
            try:
                os.unlink(temp_script)
            except:
                pass
        
    except Exception as e:
        error_details = str(e)
        logger.error(f"Error running domain parser for {domain}: {error_details}")
        return {
            "domain": domain,
            "inn": None,
            "emails": [],
            "sourceUrls": [],
            "error": f"Parser error: {error_details}"
        }


async def _save_parser_results_to_db(run_id: str, parser_run_id: str, results: List[Dict]):
    """Save domain parser results to parsing run's process_log."""
    try:
        from app.adapters.db.repositories import ParsingRunRepository
        from app.adapters.db.session import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            try:
                repo = ParsingRunRepository(session)
                parsing_run = await repo.get_by_id(run_id)
                
                if not parsing_run:
                    logger.error(f"Parsing run {run_id} not found when saving parser results")
                    return
                
                # Get existing process_log
                process_log = getattr(parsing_run, 'process_log', None)
                if isinstance(process_log, str):
                    try:
                        process_log = json.loads(process_log)
                    except json.JSONDecodeError:
                        process_log = {}
                elif not process_log:
                    process_log = {}
                
                # Ensure domain_parser structure exists
                if "domain_parser" not in process_log:
                    process_log["domain_parser"] = {"runs": {}}
                if "runs" not in process_log["domain_parser"]:
                    process_log["domain_parser"]["runs"] = {}
                
                # Save parser run results
                process_log["domain_parser"]["runs"][parser_run_id] = {
                    "status": "completed",
                    "started_at": datetime.now().isoformat(),
                    "finished_at": datetime.now().isoformat(),
                    "results": results
                }
                
                # Update parsing run
                parsing_run.process_log = json.dumps(process_log, ensure_ascii=False)
                await session.commit()
                
                logger.info(f"Saved domain parser results for run {run_id}, parser_run_id {parser_run_id}")
            except Exception as e:
                logger.error(f"Error in save transaction: {e}")
                await session.rollback()
                raise
                
    except Exception as e:
        logger.error(f"Error saving domain parser results to DB: {e}")
