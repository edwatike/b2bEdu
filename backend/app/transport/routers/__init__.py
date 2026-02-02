"""Routers module."""

from . import health
from . import moderator_suppliers
from . import moderator_users
from . import keywords
from . import blacklist
from . import parsing
from . import parsing_runs
from . import domains_queue
from . import attachments
from . import checko
from . import domain_parser
from . import auth
from . import cabinet
from . import mail

try:
    from . import comet
except Exception:
    comet = None

try:
    from . import learning
except Exception:
    learning = None

__all__ = [
    "health",
    "moderator_suppliers",
    "moderator_users",
    "keywords",
    "blacklist",
    "parsing",
    "parsing_runs",
    "domains_queue",
    "attachments",
    "checko",
    "domain_parser",
    "auth",
    "cabinet",
    "mail",
]

if comet is not None:
    __all__.append("comet")

if learning is not None:
    __all__.append("learning")
