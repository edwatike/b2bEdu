"""Database repositories for data access."""
from typing import Optional, List
from sqlalchemy import select, func, and_
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.db.base_repository import BaseRepository
from app.adapters.db.models import (
    ModeratorSupplierModel,
    KeywordModel,
    SupplierKeywordModel,
    BlacklistModel,
    ParsingRequestModel,
    ParsingRunModel,
    DomainQueueModel,
)


class ModeratorSupplierRepository:
    """Repository for moderator suppliers."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, supplier_data: dict) -> ModeratorSupplierModel:
        """Create a new supplier."""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.debug(f"Creating supplier with fields: {list(supplier_data.keys())}")
        
        # Log key fields before creation
        for key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
            if key in supplier_data:
                value = supplier_data[key]
                if isinstance(value, str) and len(value) > 50:
                    logger.info(f"  {key}: [string, length={len(value)}]")
                else:
                    logger.info(f"  {key}: {type(value).__name__} = {repr(value)}")
            else:
                logger.debug(f"  {key}: not present")
        
        supplier = ModeratorSupplierModel(**supplier_data)
        self.session.add(supplier)
        await self.session.flush()
        await self.session.refresh(supplier)
        
        # Log what was actually saved
        logger.info(f"Supplier created successfully with ID: {supplier.id}, name: {supplier.name}")
        logger.debug(f"Saved registration_date: {supplier.registration_date}")
        logger.debug(f"Saved legal_address: {supplier.legal_address[:50] if supplier.legal_address else None}")
        logger.debug(f"Saved finance_year: {supplier.finance_year}")
        logger.debug(f"Saved legal_cases_count: {supplier.legal_cases_count}")
        logger.debug(f"Saved checko_data length: {len(supplier.checko_data) if supplier.checko_data else 0}")
        
        return supplier
    
    async def get_by_id(self, supplier_id: int) -> Optional[ModeratorSupplierModel]:
        """Get supplier by ID."""
        result = await self.session.execute(
            select(ModeratorSupplierModel)
            .where(ModeratorSupplierModel.id == supplier_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_domain(self, domain: str) -> Optional[ModeratorSupplierModel]:
        """Get supplier by domain."""
        result = await self.session.execute(
            select(ModeratorSupplierModel)
            .where(ModeratorSupplierModel.domain == domain)
        )
        return result.scalar_one_or_none()
    
    async def get_by_inn(self, inn: str) -> Optional[ModeratorSupplierModel]:
        """Get supplier by INN (returns first match if multiple exist)."""
        result = await self.session.execute(
            select(ModeratorSupplierModel)
            .where(ModeratorSupplierModel.inn == inn)
            .order_by(ModeratorSupplierModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        type_filter: Optional[str] = None
    ) -> tuple[List[ModeratorSupplierModel], int]:
        """List suppliers with pagination."""
        query = select(ModeratorSupplierModel)
        count_query = select(func.count()).select_from(ModeratorSupplierModel)
        
        if type_filter:
            query = query.where(ModeratorSupplierModel.type == type_filter)
            count_query = count_query.where(ModeratorSupplierModel.type == type_filter)
        
        query = query.order_by(ModeratorSupplierModel.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        suppliers = result.scalars().all()
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        
        return list(suppliers), total
    
    async def update(self, supplier_id: int, supplier_data: dict) -> Optional[ModeratorSupplierModel]:
        """Update supplier."""
        import logging
        logger = logging.getLogger(__name__)
        
        supplier = await self.get_by_id(supplier_id)
        if not supplier:
            logger.warning(f"Supplier with ID {supplier_id} not found for update")
            return None
        
        logger.debug(f"Updating supplier ID {supplier_id} with fields: {list(supplier_data.keys())}")
        
        # Log key fields before update
        for key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
            if key in supplier_data:
                value = supplier_data[key]
                if isinstance(value, str) and len(value) > 50:
                    logger.info(f"  {key}: [string, length={len(value)}]")
                else:
                    logger.info(f"  {key}: {type(value).__name__} = {repr(value)}")
        
        # Update fields using setattr - this ensures SQLAlchemy tracks changes
        updated_fields = []
        for key, value in supplier_data.items():
            # Only update if the field exists on the model
            if hasattr(supplier, key):
                old_value = getattr(supplier, key)
                setattr(supplier, key, value)
                updated_fields.append(key)
                if key in ["registration_date", "legal_address", "finance_year", "legal_cases_count", "checko_data"]:
                    logger.debug(f"Set {key}: {type(old_value).__name__} -> {type(value).__name__}")
            else:
                logger.warning(f"Field {key} does not exist on ModeratorSupplierModel, skipping")
        
        # Flush changes to database
        await self.session.flush()
        
        # Refresh supplier to get updated data from DB
        await self.session.refresh(supplier)
        logger.info(f"Supplier ID {supplier_id} updated successfully with {len(updated_fields)} fields: {', '.join(updated_fields)}")
        return supplier
    
    async def delete(self, supplier_id: int) -> bool:
        """Delete supplier."""
        supplier = await self.get_by_id(supplier_id)
        if not supplier:
            return False
        
        await self.session.delete(supplier)
        await self.session.flush()
        return True
    
    async def get_keywords(self, supplier_id: int) -> List[dict]:
        """Get supplier keywords with metadata."""
        result = await self.session.execute(
            select(SupplierKeywordModel, KeywordModel)
            .join(KeywordModel, SupplierKeywordModel.keyword_id == KeywordModel.id)
            .where(SupplierKeywordModel.supplier_id == supplier_id)
        )
        
        keywords = []
        for supplier_keyword, keyword in result.all():
            keywords.append({
                "keyword": keyword.keyword,
                "urlCount": supplier_keyword.url_count,
                "runId": supplier_keyword.parsing_run_id,
                "firstUrl": supplier_keyword.first_url,
            })
        
        return keywords


class KeywordRepository:
    """Repository for keywords."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, keyword: str) -> KeywordModel:
        """Create a new keyword."""
        keyword_model = KeywordModel(keyword=keyword)
        self.session.add(keyword_model)
        await self.session.flush()
        await self.session.refresh(keyword_model)
        return keyword_model
    
    async def get_by_id(self, keyword_id: int) -> Optional[KeywordModel]:
        """Get keyword by ID."""
        result = await self.session.execute(
            select(KeywordModel).where(KeywordModel.id == keyword_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_keyword(self, keyword: str) -> Optional[KeywordModel]:
        """Get keyword by keyword string."""
        result = await self.session.execute(
            select(KeywordModel).where(KeywordModel.keyword == keyword)
        )
        return result.scalar_one_or_none()
    
    async def list(self) -> List[KeywordModel]:
        """List all keywords."""
        result = await self.session.execute(
            select(KeywordModel).order_by(KeywordModel.keyword)
        )
        return list(result.scalars().all())
    
    async def delete(self, keyword_id: int) -> bool:
        """Delete keyword."""
        keyword = await self.get_by_id(keyword_id)
        if not keyword:
            return False
        
        await self.session.delete(keyword)
        await self.session.flush()
        return True
    
    async def attach_to_supplier(
        self,
        supplier_id: int,
        keyword_id: int,
        url_count: int = 1,
        parsing_run_id: Optional[str] = None,
        first_url: Optional[str] = None
    ) -> SupplierKeywordModel:
        """Attach keyword to supplier."""
        supplier_keyword = SupplierKeywordModel(
            supplier_id=supplier_id,
            keyword_id=keyword_id,
            url_count=url_count,
            parsing_run_id=parsing_run_id,
            first_url=first_url
        )
        self.session.add(supplier_keyword)
        await self.session.flush()
        return supplier_keyword


class BlacklistRepository:
    """Repository for blacklist."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, blacklist_data: dict) -> BlacklistModel:
        """Add domain to blacklist."""
        blacklist_entry = BlacklistModel(**blacklist_data)
        self.session.add(blacklist_entry)
        await self.session.flush()
        await self.session.refresh(blacklist_entry)
        return blacklist_entry
    
    async def get_by_domain(self, domain: str) -> Optional[BlacklistModel]:
        """Get blacklist entry by domain."""
        result = await self.session.execute(
            select(BlacklistModel).where(BlacklistModel.domain == domain)
        )
        return result.scalar_one_or_none()
    
    async def list(self, limit: int = 100, offset: int = 0) -> tuple[List[BlacklistModel], int]:
        """List blacklist entries with pagination."""
        query = select(BlacklistModel).order_by(BlacklistModel.added_at.desc())
        count_query = select(func.count()).select_from(BlacklistModel)
        
        result = await self.session.execute(
            query.limit(limit).offset(offset)
        )
        entries = result.scalars().all()
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        
        return list(entries), total
    
    async def delete(self, domain: str) -> bool:
        """Remove domain from blacklist."""
        entry = await self.get_by_domain(domain)
        if not entry:
            return False
        
        await self.session.delete(entry)
        await self.session.flush()
        return True
    
    async def is_blacklisted(self, domain: str) -> bool:
        """Check if domain is blacklisted."""
        entry = await self.get_by_domain(domain)
        return entry is not None


class ParsingRequestRepository:
    """Repository for parsing requests."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, request_data: dict) -> ParsingRequestModel:
        """Create a new parsing request."""
        # Remove any invalid fields that might be passed by mistake
        valid_fields = {
            'id', 'created_at', 'updated_at', 'created_by', 'raw_keys_json',
            'depth', 'source', 'comment', 'title'
        }
        filtered_data = {k: v for k, v in request_data.items() if k in valid_fields}
        
        # Log if invalid fields were filtered out
        invalid_fields = set(request_data.keys()) - valid_fields
        if invalid_fields:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Filtered out invalid fields from request_data: {invalid_fields}")
        
        request = ParsingRequestModel(**filtered_data)
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get_by_id(self, request_id: int) -> Optional[ParsingRequestModel]:
        """Get parsing request by ID."""
        result = await self.session.execute(
            select(ParsingRequestModel).where(ParsingRequestModel.id == request_id)
        )
        return result.scalar_one_or_none()

    async def update(self, request_id: int, patch: dict) -> Optional[ParsingRequestModel]:
        """Update parsing request fields."""
        request = await self.get_by_id(request_id)
        if not request:
            return None

        valid_fields = {
            'raw_keys_json', 'depth', 'source', 'comment', 'title', 'created_by'
        }
        for key, value in patch.items():
            if key in valid_fields and hasattr(request, key):
                setattr(request, key, value)

        await self.session.flush()
        await self.session.refresh(request)
        return request


class ParsingRunRepository:
    """Repository for parsing runs."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, run_data: dict) -> ParsingRunModel:
        """Create a new parsing run."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Remove any invalid fields that might be passed by mistake
        valid_fields = {
            'id', 'run_id', 'request_id', 'parser_task_id', 'status', 
            'depth', 'source', 'created_at', 'started_at', 'finished_at', 
            'error_message', 'results_count'
        }
        
        # Log input data for debugging
        logger.debug(f"ParsingRunRepository.create called with: {run_data}")
        
        filtered_data = {k: v for k, v in run_data.items() if k in valid_fields}
        
        # Log if invalid fields were filtered out
        invalid_fields = set(run_data.keys()) - valid_fields
        if invalid_fields:
            logger.warning(f"Filtered out invalid fields from run_data: {invalid_fields}. Original data: {run_data}")
        
        # Double check - explicitly remove keyword if it somehow got through
        if 'keyword' in filtered_data:
            logger.error(f"ERROR: 'keyword' field found in filtered_data! This should not happen. filtered_data: {filtered_data}")
            del filtered_data['keyword']
        
        logger.debug(f"Creating ParsingRunModel with filtered_data: {filtered_data}")
        
        try:
            run = ParsingRunModel(**filtered_data)
            self.session.add(run)
            await self.session.flush()
            await self.session.refresh(run)
            return run
        except TypeError as e:
            logger.error(f"TypeError creating ParsingRunModel. filtered_data: {filtered_data}, error: {e}")
            raise
    
    async def get_by_id(self, run_id: str) -> Optional[ParsingRunModel]:
        """Get parsing run by ID."""
        from app.adapters.db.models import ParsingRequestModel
        from sqlalchemy import text
        import json
        
        # CRITICAL FIX: Always use direct SQL to avoid AttributeError
        # SQLAlchemy tries to load all columns including results_count when using select(ParsingRunModel)
        # Even if model doesn't have results_count, SQLAlchemy will try to load it from DB
        # This causes AttributeError if the model was loaded without the field
        
        # Use direct SQL to get data without triggering SQLAlchemy's column loading
        sql_result = await self.session.execute(
            text("""
                SELECT pr.id, pr.run_id, pr.request_id, pr.parser_task_id, 
                       pr.status, pr.depth, pr.source, pr.created_at, 
                       pr.started_at, pr.finished_at, pr.error_message,
                       pr.process_log
                FROM parsing_runs pr
                WHERE pr.run_id = :run_id
            """),
            {"run_id": run_id}
        )
        row = sql_result.fetchone()
        if not row:
            return None
        
        # CRITICAL FIX: Use SimpleNamespace instead of ParsingRunModel to completely avoid SQLAlchemy
        # Even object.__new__(ParsingRunModel) triggers SQLAlchemy's column loading when accessing attributes
        from types import SimpleNamespace
        run = SimpleNamespace()
        run.id = row[0]
        run.run_id = row[1]
        run.request_id = row[2]
        run.parser_task_id = row[3]
        run.status = row[4]
        run.depth = row[5]
        run.source = row[6]
        run.created_at = row[7]
        run.started_at = row[8]
        run.finished_at = row[9]
        run.error_message = row[10]
        process_log_value = row[11] if len(row) > 11 else None
        if isinstance(process_log_value, dict):
            run.process_log = process_log_value
        elif isinstance(process_log_value, str):
            try:
                parsed = json.loads(process_log_value)
                run.process_log = parsed if isinstance(parsed, dict) else None
            except Exception:
                run.process_log = None
        else:
            run.process_log = None
        
        # Load request separately using select (this should work)
        try:
            request_result = await self.session.execute(
                select(ParsingRequestModel).where(ParsingRequestModel.id == row[2])
            )
            run.request = request_result.scalar_one_or_none()
        except Exception:
            # If loading request fails, set to None
            run.request = None
        
        return run
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[ParsingRunModel], int]:
        """List parsing runs with pagination, filtering, and sorting."""
        from app.adapters.db.models import ParsingRequestModel
        from sqlalchemy import text
        from types import SimpleNamespace

        try:
            # Join with parsing_requests and eager load relationship
            query = (
                select(ParsingRunModel)
                .join(ParsingRequestModel, ParsingRunModel.request_id == ParsingRequestModel.id)
                .options(selectinload(ParsingRunModel.request))
            )

            # Фильтрация по статусу
            if status:
                query = query.where(ParsingRunModel.status == status)

            # Фильтрация по keyword (через parsing_requests)
            if keyword:
                query = query.where(
                    (ParsingRequestModel.title.ilike(f"%{keyword}%")) |
                    (ParsingRequestModel.raw_keys_json.ilike(f"%{keyword}%"))
                )

            # Сортировка
            sort_column = getattr(ParsingRunModel, sort_by, ParsingRunModel.created_at)
            if sort_order == "asc":
                query = query.order_by(sort_column.asc().nulls_last())
            else:
                query = query.order_by(sort_column.desc().nulls_last())

            # Count query с теми же фильтрами
            count_query = (
                select(func.count())
                .select_from(ParsingRunModel)
                .join(ParsingRequestModel, ParsingRunModel.request_id == ParsingRequestModel.id)
            )
            if status:
                count_query = count_query.where(ParsingRunModel.status == status)
            if keyword:
                count_query = count_query.where(
                    (ParsingRequestModel.title.ilike(f"%{keyword}%")) |
                    (ParsingRequestModel.raw_keys_json.ilike(f"%{keyword}%"))
                )

            result = await self.session.execute(
                query.limit(limit).offset(offset)
            )
            runs = result.scalars().all()

            count_result = await self.session.execute(count_query)
            total = count_result.scalar() or 0

            return list(runs), total
        except Exception as e:
            # Legacy schema fallback: parsing_runs table may not have request_id yet
            msg = str(getattr(e, "orig", e))
            if "parsing_runs.request_id" not in msg and "column parsing_runs.request_id" not in msg and "request_id" not in msg:
                raise

            # Ensure session is usable after a failed statement (PostgreSQL aborts the transaction)
            try:
                await self.session.rollback()
            except Exception:
                pass

            valid_sort_fields = {"run_id", "status", "created_at", "started_at", "finished_at"}
            safe_sort_by = sort_by if sort_by in valid_sort_fields else "created_at"
            safe_sort_order = "asc" if sort_order == "asc" else "desc"

            where_clauses: list[str] = []
            params: dict = {"limit": limit, "offset": offset}
            if status:
                where_clauses.append("status = :status")
                params["status"] = status
            if keyword:
                where_clauses.append("keyword ILIKE :keyword")
                params["keyword"] = f"%{keyword}%"

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            sql = text(
                f"""
                SELECT run_id, keyword, status, started_at, finished_at, error, results_count, created_at
                FROM parsing_runs
                {where_sql}
                ORDER BY {safe_sort_by} {safe_sort_order} NULLS LAST
                LIMIT :limit OFFSET :offset
                """
            )

            count_sql = text(
                f"""
                SELECT COUNT(*)
                FROM parsing_runs
                {where_sql}
                """
            )

            sql_result = await self.session.execute(sql, params)
            rows = sql_result.fetchall()

            count_result = await self.session.execute(count_sql, params)
            total = int(count_result.scalar() or 0)

            runs: list[SimpleNamespace] = []
            for row in rows:
                run = SimpleNamespace()
                run.run_id = row[0]
                run.keyword = row[1]
                run.status = row[2]
                run.started_at = row[3]
                run.finished_at = row[4]
                run.error_message = row[5]
                run.results_count = row[6]
                run.created_at = row[7]
                run.depth = None
                run.source = None
                run.request = None
                runs.append(run)

            return runs, total
    
    async def update(self, run_id: str, run_data: dict) -> Optional[ParsingRunModel]:
        """Update parsing run."""
        from sqlalchemy import text
        
        # CRITICAL FIX: Use direct SQL UPDATE because get_by_id() returns SimpleNamespace
        # SimpleNamespace is not a SQLAlchemy model, so setattr() won't update the database
        # We need to use direct SQL UPDATE to actually update the database
        
        if not run_data:
            # If no data to update, just return the existing run
            return await self.get_by_id(run_id)
        
        # Build UPDATE query dynamically
        valid_fields = {
            'status', 'parser_task_id', 'depth', 'source', 
            'started_at', 'finished_at', 'error_message', 'results_count'
        }
        
        # Filter out invalid fields
        filtered_data = {k: v for k, v in run_data.items() if k in valid_fields}
        
        if not filtered_data:
            # No valid fields to update
            return await self.get_by_id(run_id)
        
        # Build SET clause
        set_clauses = []
        params = {"run_id": run_id}
        
        for key, value in filtered_data.items():
            param_name = f"val_{key}"
            set_clauses.append(f"{key} = :{param_name}")
            params[param_name] = value
        
        set_clause = ", ".join(set_clauses)
        
        # Execute UPDATE
        await self.session.execute(
            text(f"""
                UPDATE parsing_runs 
                SET {set_clause}
                WHERE run_id = :run_id
            """),
            params
        )
        await self.session.flush()
        
        # Return updated run
        return await self.get_by_id(run_id)
    
    async def delete(self, run_id: str) -> bool:
        """Delete parsing run by run_id."""
        from sqlalchemy import text
        
        # CRITICAL FIX: Use direct SQL to delete, because get_by_id returns SimpleNamespace
        # which cannot be used with session.delete()
        result = await self.session.execute(
            text("DELETE FROM parsing_runs WHERE run_id = :run_id"),
            {"run_id": run_id}
        )
        await self.session.flush()
        
        # Check if any row was deleted
        return result.rowcount > 0


class DomainQueueRepository(BaseRepository):
    """Repository for domains queue."""
    
    async def create(self, queue_data: dict) -> DomainQueueModel:
        """Add domain to queue with automatic sequence error handling."""
        try:
            queue_entry = DomainQueueModel(**queue_data)
            self.session.add(queue_entry)
            await self.session.flush()
            await self.session.refresh(queue_entry)
            return queue_entry
        except Exception as e:
            # Use base class method to handle sequence errors
            if await self._handle_sequence_error(e, "domains_queue"):
                # Retry create after fixing permissions
                queue_entry = DomainQueueModel(**queue_data)
                self.session.add(queue_entry)
                await self.session.flush()
                await self.session.refresh(queue_entry)
                return queue_entry
            else:
                # Not a sequence error or couldn't fix it
                raise
    
    async def get_by_domain(self, domain: str) -> Optional[DomainQueueModel]:
        """Get queue entry by domain (returns first match, use list() for filtering by keyword/run_id)."""
        result = await self.session.execute(
            select(DomainQueueModel).where(DomainQueueModel.domain == domain).limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_by_domain_keyword_run(
        self, 
        domain: str, 
        keyword: str, 
        parsing_run_id: str
    ) -> Optional[DomainQueueModel]:
        """Get queue entry by domain, keyword, and parsing_run_id."""
        result = await self.session.execute(
            select(DomainQueueModel).where(
                DomainQueueModel.domain == domain,
                DomainQueueModel.keyword == keyword,
                DomainQueueModel.parsing_run_id == parsing_run_id
            )
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        parsing_run_id: Optional[str] = None  # Added parsing_run_id filter
    ) -> tuple[List[DomainQueueModel], int]:
        """List queue entries with pagination.
        
        IMPORTANT: Filtering logic:
        - If parsing_run_id is provided, filter ONLY by parsing_run_id (most specific)
        - If keyword is provided (and no parsing_run_id), filter by keyword
        - If both are provided, filter by BOTH (AND condition)
        - Status filter is always applied if provided
        """
        import logging
        logger = logging.getLogger(__name__)
        
        query = select(DomainQueueModel)
        count_query = select(func.count()).select_from(DomainQueueModel)
        
        filters_applied = []
        
        # Filter by status (always applied if provided)
        if status:
            status = status.strip() if isinstance(status, str) else status
            if status:
                query = query.where(DomainQueueModel.status == status)
                count_query = count_query.where(DomainQueueModel.status == status)
                filters_applied.append(f"status={status}")
        
        # Filter by parsing_run_id (most specific filter - takes priority)
        if parsing_run_id:
            parsing_run_id = parsing_run_id.strip() if isinstance(parsing_run_id, str) else parsing_run_id
            if parsing_run_id:
                query = query.where(DomainQueueModel.parsing_run_id == parsing_run_id)
                count_query = count_query.where(DomainQueueModel.parsing_run_id == parsing_run_id)
                filters_applied.append(f"parsing_run_id={parsing_run_id}")
                logger.info(f"DomainQueueRepository.list: filtering by parsing_run_id={parsing_run_id}")
        
        # Filter by keyword (applied if provided, AND with parsing_run_id if both provided)
        if keyword:
            keyword = keyword.strip() if isinstance(keyword, str) else keyword
            if keyword:
                query = query.where(DomainQueueModel.keyword.ilike(f"%{keyword}%"))
                count_query = count_query.where(DomainQueueModel.keyword.ilike(f"%{keyword}%"))
                filters_applied.append(f"keyword={keyword}")
                logger.info(f"DomainQueueRepository.list: filtering by keyword={keyword}")
        
        # Log applied filters
        if filters_applied:
            logger.info(f"DomainQueueRepository.list: applied filters: {', '.join(filters_applied)}")
        else:
            logger.warning("DomainQueueRepository.list: NO FILTERS APPLIED - returning ALL entries!")
        
        query = query.order_by(DomainQueueModel.created_at.desc())
        
        result = await self.session.execute(
            query.limit(limit).offset(offset)
        )
        entries = result.scalars().all()
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        
        logger.info(f"DomainQueueRepository.list: returning {len(entries)} entries (total={total}) with filters: {filters_applied}")
        
        return list(entries), total
    
    async def delete(self, domain: str) -> bool:
        """Remove domain from queue."""
        entry = await self.get_by_domain(domain)
        if not entry:
            return False
        
        await self.session.delete(entry)
        await self.session.flush()
        return True

