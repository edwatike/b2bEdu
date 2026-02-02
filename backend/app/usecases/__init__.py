"""Use cases module exports."""
# Import execute functions directly from modules to avoid circular imports
from app.usecases.create_moderator_supplier import execute as _create_moderator_supplier_execute
from app.usecases.get_moderator_supplier import execute as _get_moderator_supplier_execute
from app.usecases.list_moderator_suppliers import execute as _list_moderator_suppliers_execute
from app.usecases.update_moderator_supplier import execute as _update_moderator_supplier_execute
from app.usecases.delete_moderator_supplier import execute as _delete_moderator_supplier_execute
from app.usecases.get_supplier_keywords import execute as _get_supplier_keywords_execute
from app.usecases.create_keyword import execute as _create_keyword_execute
from app.usecases.list_keywords import execute as _list_keywords_execute
from app.usecases.delete_keyword import execute as _delete_keyword_execute
from app.usecases.attach_keywords import execute as _attach_keywords_execute
from app.usecases.add_to_blacklist import execute as _add_to_blacklist_execute
from app.usecases.list_blacklist import execute as _list_blacklist_execute
from app.usecases.remove_from_blacklist import execute as _remove_from_blacklist_execute
from app.usecases.start_parsing import execute as _start_parsing_execute
from app.usecases.get_parsing_status import execute as _get_parsing_status_execute
from app.usecases.get_parsing_run import execute as _get_parsing_run_execute
from app.usecases.list_parsing_runs import execute as _list_parsing_runs_execute
from app.usecases.delete_parsing_run import execute as _delete_parsing_run_execute
from app.usecases.list_domains_queue import execute as _list_domains_queue_execute
from app.usecases.remove_from_domains_queue import execute as _remove_from_domains_queue_execute
from app.usecases.get_checko_data import execute as _get_checko_data_execute

# Create wrapper objects with execute method for compatibility with routers
class UseCaseWrapper:
    def __init__(self, execute_func):
        self.execute = execute_func

create_moderator_supplier = UseCaseWrapper(_create_moderator_supplier_execute)
get_moderator_supplier = UseCaseWrapper(_get_moderator_supplier_execute)
list_moderator_suppliers = UseCaseWrapper(_list_moderator_suppliers_execute)
update_moderator_supplier = UseCaseWrapper(_update_moderator_supplier_execute)
delete_moderator_supplier = UseCaseWrapper(_delete_moderator_supplier_execute)
get_supplier_keywords = UseCaseWrapper(_get_supplier_keywords_execute)
create_keyword = UseCaseWrapper(_create_keyword_execute)
list_keywords = UseCaseWrapper(_list_keywords_execute)
delete_keyword = UseCaseWrapper(_delete_keyword_execute)
attach_keywords = UseCaseWrapper(_attach_keywords_execute)
add_to_blacklist = UseCaseWrapper(_add_to_blacklist_execute)
list_blacklist = UseCaseWrapper(_list_blacklist_execute)
remove_from_blacklist = UseCaseWrapper(_remove_from_blacklist_execute)
start_parsing = UseCaseWrapper(_start_parsing_execute)
get_parsing_status = UseCaseWrapper(_get_parsing_status_execute)
get_parsing_run = UseCaseWrapper(_get_parsing_run_execute)
list_parsing_runs = UseCaseWrapper(_list_parsing_runs_execute)
delete_parsing_run = UseCaseWrapper(_delete_parsing_run_execute)
list_domains_queue = UseCaseWrapper(_list_domains_queue_execute)
remove_from_domains_queue = UseCaseWrapper(_remove_from_domains_queue_execute)
get_checko_data = UseCaseWrapper(_get_checko_data_execute)

__all__ = [
    "create_moderator_supplier",
    "get_moderator_supplier",
    "list_moderator_suppliers",
    "update_moderator_supplier",
    "delete_moderator_supplier",
    "get_supplier_keywords",
    "create_keyword",
    "list_keywords",
    "delete_keyword",
    "attach_keywords",
    "add_to_blacklist",
    "list_blacklist",
    "remove_from_blacklist",
    "start_parsing",
    "get_parsing_status",
    "get_parsing_run",
    "list_parsing_runs",
    "delete_parsing_run",
    "list_domains_queue",
    "remove_from_domains_queue",
    "get_checko_data",
]
