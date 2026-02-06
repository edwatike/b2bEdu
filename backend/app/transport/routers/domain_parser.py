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
from app.utils.domain import normalize_domain_root

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for parser runs status
_parser_runs: Dict[str, Dict] = {}


@router.get("/moderation-domains")
async def list_moderation_domains(limit: int = 5000):
    """List globally blocked domains that require moderation."""
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text(
                "SELECT domain FROM domain_moderation "
                "WHERE COALESCE(status, 'requires_moderation') = 'requires_moderation' "
                "ORDER BY created_at DESC "
                "LIMIT :limit"
            ),
            {"limit": int(max(1, min(limit, 20000)))},
        )
        domains = [str(r[0]) for r in (res.fetchall() or []) if r and r[0]]
    return {"domains": domains, "total": len(domains)}


async def _domain_exists_in_suppliers(domain: str) -> bool:
    """Check whether domain is already present in moderator_suppliers/supplier_domains.

    Uses normalized root comparison and strips optional 'www.' prefix.
    """
    norm = _normalize_domain(domain)
    if not norm:
        return False
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text(
                "SELECT 1 "
                "FROM moderator_suppliers ms "
                "LEFT JOIN supplier_domains sd ON sd.supplier_id = ms.id "
                "WHERE replace(lower(COALESCE(sd.domain, ms.domain, '')), 'www.', '') = :d "
                "LIMIT 1"
            ),
            {"d": norm},
        )
        return res.fetchone() is not None


async def _domain_requires_moderation(domain: str) -> bool:
    norm = _normalize_domain(domain)
    if not norm:
        return False
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            text(
                "SELECT 1 FROM domain_moderation "
                "WHERE replace(lower(domain), 'www.', '') = :d "
                "AND COALESCE(status, 'requires_moderation') = 'requires_moderation' "
                "LIMIT 1"
            ),
            {"d": norm},
        )
        return res.fetchone() is not None


async def _mark_domain_requires_moderation(domain: str, reason: str = "inn_not_found") -> None:
    norm = _normalize_domain(domain)
    if not norm:
        return
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "INSERT INTO domain_moderation (domain, status, reason) "
                "VALUES (:d, 'requires_moderation', :reason) "
                "ON CONFLICT (domain) DO UPDATE SET "
                "status='requires_moderation', reason=EXCLUDED.reason"
            ),
            {"d": norm, "reason": reason[:200]},
        )
        await db.commit()


async def _sync_domain_parser_auto_progress(
    *,
    run_id: str,
    parser_run_id: str,
    processed: int,
    total: int,
    status: str | None = None,
    last_domain: str | None = None,
    error: str | None = None,
) -> None:
    """Persist live auto-enrichment progress into parsing_runs.process_log.domain_parser_auto."""
    from sqlalchemy import text
    from app.adapters.db.session import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            row = res.fetchone()
            pl = row[0] if row else None
            if isinstance(pl, str):
                try:
                    pl = json.loads(pl)
                except Exception:
                    pl = None
            if not isinstance(pl, dict):
                pl = {}
            dp = pl.get("domain_parser_auto")
            if not isinstance(dp, dict):
                dp = {}
            if str(dp.get("parserRunId") or "") != str(parser_run_id):
                return
            dp["processed"] = int(processed)
            dp["total"] = int(total)
            if status:
                dp["status"] = str(status)
            if last_domain:
                dp["lastDomain"] = str(last_domain)
            if error:
                dp["error"] = str(error)[:800]
            if status in {"completed", "failed"}:
                dp["finishedAt"] = datetime.now().isoformat()
            pl["domain_parser_auto"] = dp
            await db.execute(
                text("UPDATE parsing_runs SET process_log = CAST(:process_log AS jsonb) WHERE run_id = :run_id"),
                {"process_log": json.dumps(pl, ensure_ascii=False), "run_id": run_id},
            )
            await db.commit()
    except Exception:
        logger.warning("Failed to sync domain_parser_auto progress for run_id=%s", run_id, exc_info=True)


def _normalize_domain(domain: str) -> str:
    return normalize_domain_root(domain)


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
            "currentDomain": None,
            "currentSourceUrls": [],
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
        currentDomain=run_data.get("currentDomain"),
        currentSourceUrls=run_data.get("currentSourceUrls", []) or [],
        results=run_data["results"]
    )


async def _process_domain_parser_batch(parser_run_id: str, run_id: str, domains: List[str]):
    """Background task to process domain parser batch."""
    logger.info(f"=== PROCESSING DOMAIN PARSER BATCH ===")
    logger.info(f"Parser Run ID: {parser_run_id}")
    logger.info(f"Domains: {len(domains)}")
    
    results = []
    
    try:
        base_processed = int(_parser_runs.get(parser_run_id, {}).get("baseProcessed") or 0)
        overall_total = int(_parser_runs.get(parser_run_id, {}).get("overallTotal") or len(domains))
        for i, domain in enumerate(domains):
            logger.info(f"Processing domain {i+1}/{len(domains)}: {domain}")
            _parser_runs[parser_run_id]["currentDomain"] = _normalize_domain(domain)
            _parser_runs[parser_run_id]["currentSourceUrls"] = []
            
            try:
                # Optimization: if domain already exists as a supplier, skip heavy parsing/enrichment.
                if await _domain_exists_in_suppliers(domain):
                    result = {
                        "domain": _normalize_domain(domain),
                        "inn": None,
                        "emails": [],
                        "sourceUrls": [],
                        "error": None,
                        "skipped": True,
                        "reason": "supplier_exists",
                    }
                elif await _domain_requires_moderation(domain):
                    result = {
                        "domain": _normalize_domain(domain),
                        "inn": None,
                        "emails": [],
                        "sourceUrls": [],
                        "error": None,
                        "skipped": True,
                        "reason": "requires_moderation",
                    }
                else:
                    result = await _run_domain_parser_for_domain(domain)
                try:
                    result["domain"] = _normalize_domain(result.get("domain") or domain)
                except Exception:
                    pass
                _parser_runs[parser_run_id]["currentSourceUrls"] = list(result.get("sourceUrls") or [])
                results.append(result)
                
                # Update status
                processed_global = min(overall_total, base_processed + i + 1)
                _parser_runs[parser_run_id]["processed"] = processed_global
                _parser_runs[parser_run_id]["total"] = overall_total
                _parser_runs[parser_run_id]["results"] = results
                await _sync_domain_parser_auto_progress(
                    run_id=run_id,
                    parser_run_id=parser_run_id,
                    processed=processed_global,
                    total=overall_total,
                    status="running",
                    last_domain=result.get("domain") or domain,
                )
                
                logger.info(f"Domain {domain} processed: INN={result.get('inn')}, Emails={result.get('emails')}")

                # If INN was not found, mark domain as requiring moderation globally.
                if (
                    not str(result.get("inn") or "").strip()
                    and not str(result.get("error") or "").strip()
                    and str(result.get("reason") or "") not in {"supplier_exists", "requires_moderation"}
                ):
                    try:
                        await _mark_domain_requires_moderation(result.get("domain") or domain, "inn_not_found")
                        result["dataStatus"] = "requires_moderation"
                    except Exception:
                        logger.warning("Failed to mark domain requires_moderation: %s", domain, exc_info=True)

                # Progressive enrichment: upsert supplier (and Checko) as soon as we have a result.
                # This allows cabinet/moderator tables to be updated gradually during the batch.
                try:
                    await _upsert_suppliers_from_domain_parser_results([result])
                except Exception as e:
                    logger.error(f"Progressive supplier upsert failed for domain {domain}: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error processing domain {domain}: {e}")
                results.append({
                    "domain": domain,
                    "inn": None,
                    "emails": [],
                    "sourceUrls": [],
                    "error": str(e)
                })
                processed_global = min(overall_total, base_processed + i + 1)
                _parser_runs[parser_run_id]["processed"] = processed_global
                _parser_runs[parser_run_id]["total"] = overall_total
                _parser_runs[parser_run_id]["results"] = results
                await _sync_domain_parser_auto_progress(
                    run_id=run_id,
                    parser_run_id=parser_run_id,
                    processed=processed_global,
                    total=overall_total,
                    status="running",
                    last_domain=domain,
                    error=str(e),
                )
        
        # Mark as completed
        _parser_runs[parser_run_id]["status"] = "completed"
        _parser_runs[parser_run_id]["finishedAt"] = datetime.now().isoformat()
        _parser_runs[parser_run_id]["processed"] = min(overall_total, base_processed + len(domains))
        _parser_runs[parser_run_id]["total"] = overall_total
        await _sync_domain_parser_auto_progress(
            run_id=run_id,
            parser_run_id=parser_run_id,
            processed=int(_parser_runs[parser_run_id]["processed"]),
            total=overall_total,
            status="completed",
        )
        
        # Save results to database
        await _save_parser_results_to_db(run_id, parser_run_id, results)

        # Enrich suppliers DB (moderator_suppliers) + Checko when INN is found
        try:
            await _upsert_suppliers_from_domain_parser_results(results)
        except Exception as e:
            logger.error(f"Failed to upsert suppliers from domain parser results: {e}", exc_info=True)
        
        logger.info(f"Domain parser batch completed: {parser_run_id}")
    except Exception as e:
        logger.error(f"Error in domain parser batch: {e}")
        _parser_runs[parser_run_id]["status"] = "failed"
        _parser_runs[parser_run_id]["error"] = str(e)
        await _sync_domain_parser_auto_progress(
            run_id=run_id,
            parser_run_id=parser_run_id,
            processed=int(_parser_runs.get(parser_run_id, {}).get("processed") or 0),
            total=int(_parser_runs.get(parser_run_id, {}).get("total") or len(domains)),
            status="failed",
            error=str(e),
        )


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
        from app.adapters.db.session import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            try:
                res = await session.execute(
                    text("SELECT process_log FROM parsing_runs WHERE run_id = :run_id"),
                    {"run_id": run_id},
                )
                row = res.fetchone()
                if not row:
                    logger.error(f"Parsing run {run_id} not found when saving parser results")
                    return

                # Get existing process_log
                process_log = row[0]
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

                # Update parsing run (direct SQL to avoid SimpleNamespace)
                await session.execute(
                    text(
                        "UPDATE parsing_runs SET process_log = CAST(:process_log AS jsonb) WHERE run_id = :run_id"
                    ),
                    {
                        "process_log": json.dumps(process_log, ensure_ascii=False),
                        "run_id": run_id,
                    },
                )
                await session.commit()
                
                logger.info(f"Saved domain parser results for run {run_id}, parser_run_id {parser_run_id}")
            except Exception as e:
                logger.error(f"Error in save transaction: {e}")
                await session.rollback()
                raise
                
    except Exception as e:
        logger.error(f"Error saving domain parser results to DB: {e}")


async def _upsert_suppliers_from_domain_parser_results(results: List[Dict]) -> None:
    """Best-effort: create/update moderator_suppliers from extracted INN/emails and enrich via Checko."""
    from app.adapters.db.session import AsyncSessionLocal
    from app.adapters.db.repositories import ModeratorSupplierRepository
    from app.usecases import get_checko_data, update_moderator_supplier, create_moderator_supplier

    async with AsyncSessionLocal() as db:
        repo = ModeratorSupplierRepository(db)

        for r in results or []:
            try:
                domain_raw = str((r or {}).get("domain") or "").strip()
                domain = _normalize_domain(domain_raw)
                inn = str((r or {}).get("inn") or "").strip()
                emails = (r or {}).get("emails") or []
                if not isinstance(emails, list):
                    emails = []
                emails = [str(x).strip().lower() for x in emails if str(x).strip()]
                email = emails[0] if emails else None

                # Only auto-enrich if INN + email exists (as requested)
                if not domain or not inn or not email:
                    continue

                # INN uniqueness:
                # if INN already exists on another supplier, bind this domain to that supplier
                # instead of skipping the record, so run UI can reflect supplier/checko status.
                existing_by_inn = await repo.get_by_inn(inn)
                linked_by_inn = False
                supplier = await repo.get_by_domain(domain)
                if existing_by_inn is not None and not bool(getattr(existing_by_inn, "allow_duplicate_inn", False)):
                    supplier = existing_by_inn
                    linked_by_inn = True
                    r["conflictInn"] = True
                    r["conflictSupplierId"] = int(existing_by_inn.id)
                    r["supplierLinkedByInn"] = True

                    # Ensure the discovered domain/email become attached to the existing supplier.
                    try:
                        await repo.add_domain(int(supplier.id), domain, is_primary=False)
                        for idx, em in enumerate(emails):
                            await repo.add_email(int(supplier.id), em, is_primary=bool(idx == 0))
                    except Exception:
                        pass

                    # Keep primary contacts fresh if missing on supplier card.
                    await update_moderator_supplier.execute(
                        db=db,
                        supplier_id=int(supplier.id),
                        supplier_data={
                            "domain": getattr(supplier, "domain", None) or domain,
                            "email": getattr(supplier, "email", None) or email,
                        },
                    )

                    # Checko block below is still executed for the resolved supplier.

                if supplier is None:
                    # Minimal creation (name is required)
                    supplier = await create_moderator_supplier.execute(
                        db=db,
                        supplier_data={
                            "name": domain,
                            "domain": domain,
                            "inn": inn,
                            "email": email,
                            "type": "supplier",
                            "data_status": "needs_checko",
                        },
                    )
                    r["supplierCreated"] = True
                elif not linked_by_inn:
                    # Update basic extracted contacts
                    await update_moderator_supplier.execute(
                        db=db,
                        supplier_id=int(supplier.id),
                        supplier_data={
                            "domain": domain,
                            "inn": inn,
                            "email": email,
                        },
                    )
                    r["supplierUpdated"] = True

                # Persist domains/emails list
                try:
                    await repo.add_domain(int(supplier.id), domain, is_primary=True)
                    for idx, em in enumerate(emails):
                        await repo.add_email(int(supplier.id), em, is_primary=bool(idx == 0))
                except Exception:
                    pass

                # Always fetch Checko data when INN exists
                try:
                    checko = await get_checko_data.execute(db=db, inn=inn, force_refresh=False)
                    # Map frontend keys into supplier update fields (usecase normalizes camelCase)
                    await update_moderator_supplier.execute(
                        db=db,
                        supplier_id=int(supplier.id),
                        supplier_data={
                            "name": checko.get("name") or domain,
                            "ogrn": checko.get("ogrn"),
                            "kpp": checko.get("kpp"),
                            "okpo": checko.get("okpo"),
                            "companyStatus": checko.get("companyStatus"),
                            "registrationDate": checko.get("registrationDate"),
                            "legalAddress": checko.get("legalAddress"),
                            "phone": checko.get("phone"),
                            "website": checko.get("website"),
                            "vk": checko.get("vk"),
                            "telegram": checko.get("telegram"),
                            "authorizedCapital": checko.get("authorizedCapital"),
                            "revenue": checko.get("revenue"),
                            "profit": checko.get("profit"),
                            "financeYear": checko.get("financeYear"),
                            "legalCasesCount": checko.get("legalCasesCount"),
                            "legalCasesSum": checko.get("legalCasesSum"),
                            "legalCasesAsPlaintiff": checko.get("legalCasesAsPlaintiff"),
                            "legalCasesAsDefendant": checko.get("legalCasesAsDefendant"),
                            "checkoData": checko.get("checkoData"),
                            "data_status": "complete",
                        },
                    )
                    r["dataStatus"] = "complete"
                except Exception as e:
                    logger.warning(f"Checko enrich failed for domain={domain}, inn={inn}: {e}")
                    try:
                        await update_moderator_supplier.execute(
                            db=db,
                            supplier_id=int(supplier.id),
                            supplier_data={
                                "data_status": "needs_checko",
                            },
                        )
                        r["dataStatus"] = "needs_checko"
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Supplier upsert failed for domain parser result {r}: {e}")

        await db.commit()
