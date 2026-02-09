"""Domain normalization helpers."""
from __future__ import annotations


def normalize_domain_root(domain: str | None) -> str:
    """Normalize to root domain (e.g., spb.example.com -> example.com)."""
    if not domain:
        return ""
    d = str(domain).strip().lower()
    if not d:
        return ""
    # Remove protocol and path
    if "://" in d:
        try:
            from urllib.parse import urlparse

            d = urlparse(d).netloc or d
        except Exception:
            pass
    d = d.split("/")[0].strip()
    if d.startswith("www."):
        d = d[4:]
    parts = [p for p in d.split(".") if p]
    if len(parts) >= 2:
        d = ".".join(parts[-2:])

    # Normalize regional suffixes in the second-level label (e.g., kraska-spb.ru -> kraska.ru)
    try:
        label, tld = d.split(".", 1)
        for suffix in ("spb", "ekb"):
            tail = f"-{suffix}"
            if label.endswith(tail) and len(label) > len(tail):
                label = label[: -len(tail)]
                d = f"{label}.{tld}" if tld else label
                break
    except Exception:
        pass

    return d


def normalize_domain_for_compare(domain: str | None) -> str:
    """Normalize for comparisons (root domain)."""
    return normalize_domain_root(domain)
