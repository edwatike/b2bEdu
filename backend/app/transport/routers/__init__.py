"""Routers package.

Keep this module side-effect free: importing the package must not eagerly import
all router modules. This prevents startup hangs and circular-import cascades.
"""

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
    "learning",
]

