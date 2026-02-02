"""Base repository class with sequence error handling."""
from typing import Optional
from sqlalchemy import text
import logging


class BaseRepository:
    """Base class for repositories with automatic sequence error handling."""
    
    def __init__(self, session):
        self.session = session
        self.logger = logging.getLogger(__name__)
    
    async def _fix_sequence_permissions(self, table_name: str) -> bool:
        """Fix sequence permissions for a table.
        
        Args:
            table_name: Name of the table (without schema)
            
        Returns:
            True if sequence was fixed, False otherwise
        """
        sequence_names = [
            f"{table_name}_id_seq",
            f"{table_name}_new_id_seq",
            f"{table_name}_new_id_seq1"
        ]
        
        expected_name = f"{table_name}_id_seq"
        
        for old_name in sequence_names:
            try:
                # Check if sequence exists
                check_query = text(
                    "SELECT sequence_name FROM information_schema.sequences "
                    "WHERE sequence_name = :seq_name"
                )
                result = await self.session.execute(check_query, {"seq_name": old_name})
                exists = result.scalar_one_or_none() is not None
                
                if exists and old_name != expected_name:
                    # Rename sequence to standard name
                    rename_query = text(f"ALTER SEQUENCE {old_name} RENAME TO {expected_name}")
                    await self.session.execute(rename_query)
                    await self.session.commit()
                    self.logger.info(f"Renamed sequence {old_name} to {expected_name}")
                
                # Grant permissions on the correct sequence name
                if exists or old_name == expected_name:
                    grant_query = text(f"""
                        GRANT ALL PRIVILEGES ON SEQUENCE {expected_name} TO postgres;
                        GRANT ALL PRIVILEGES ON SEQUENCE {expected_name} TO PUBLIC;
                        ALTER SEQUENCE {expected_name} OWNER TO postgres;
                    """)
                    await self.session.execute(grant_query)
                    await self.session.commit()
                    self.logger.info(f"Fixed permissions on sequence {expected_name}")
                    return True
                    
            except Exception as e:
                await self.session.rollback()
                self.logger.warning(f"Could not fix sequence {old_name}: {e}")
                continue
        
        return False
    
    async def _handle_sequence_error(self, error: Exception, table_name: str) -> bool:
        """Handle sequence-related errors automatically.
        
        Args:
            error: The exception that occurred
            table_name: Name of the table that uses the sequence
            
        Returns:
            True if error was handled and can be retried, False otherwise
        """
        error_str = str(error)
        
        # Check if this is a sequence-related error
        is_sequence_error = (
            "InsufficientPrivilegeError" in error_str or
            "sequence" in error_str.lower() or
            "_seq" in error_str.lower()
        )
        
        if not is_sequence_error:
            return False
        
        self.logger.error(f"Sequence permission error for {table_name}: {error}")
        
        # Rollback to clear the failed transaction
        await self.session.rollback()
        
        # Try to fix sequence permissions
        if await self._fix_sequence_permissions(table_name):
            self.logger.info(f"Successfully fixed sequence permissions for {table_name}")
            return True
        else:
            self.logger.error(f"Failed to fix sequence permissions for {table_name}")
            return False













