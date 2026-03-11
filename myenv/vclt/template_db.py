import json
import os
import re
from difflib import SequenceMatcher

from vclt.config import (
    TEMPLATE_CURATED_MODE,
    TEMPLATE_EXCLUDED_CATEGORY_KEYWORDS,
    TEMPLATE_EXCLUDED_NAME_KEYWORDS,
    TEMPLATE_INDEX_CACHE,
    TEMPLATE_LIBRARY_DIR,
    logger,
)


def _normalize_text(text):
    text = (text or "").lower()
    text = text.replace(".asc", "")
    text = re.sub(r"[_\-/]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text):
    return {token for token in _normalize_text(text).split() if len(token) > 1}


def _is_allowed_template(category, display_name):
    if not TEMPLATE_CURATED_MODE:
        return True

    normalized_category = _normalize_text(category)
    normalized_name = _normalize_text(display_name)

    for keyword in TEMPLATE_EXCLUDED_CATEGORY_KEYWORDS:
        if _normalize_text(keyword) in normalized_category:
            return False

    for keyword in TEMPLATE_EXCLUDED_NAME_KEYWORDS:
        if _normalize_text(keyword) in normalized_name:
            return False

    return True


def scan_template_library(library_dir=None):
    base_dir = library_dir or TEMPLATE_LIBRARY_DIR
    if not base_dir or not os.path.isdir(base_dir):
        return []

    entries = []
    for root, _, files in os.walk(base_dir):
        for file_name in files:
            if not file_name.lower().endswith(".asc"):
                continue
            abs_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(abs_path, base_dir)
            rel_parts = rel_path.split(os.sep)
            category = rel_parts[0] if rel_parts else ""
            display_name = os.path.splitext(file_name)[0].replace("-", " ")
            if not _is_allowed_template(category, display_name):
                continue
            normalized_name = _normalize_text(display_name)
            normalized_relpath = _normalize_text(rel_path)
            tokens = sorted(_tokenize(f"{category} {display_name} {rel_path}"))
            entries.append(
                {
                    "name": display_name,
                    "category": category,
                    "path": abs_path,
                    "relpath": rel_path,
                    "normalized_name": normalized_name,
                    "normalized_relpath": normalized_relpath,
                    "tokens": tokens,
                }
            )

    entries.sort(key=lambda entry: (entry["category"].lower(), entry["name"].lower()))
    return entries


def refresh_template_index(library_dir=None):
    entries = scan_template_library(library_dir=library_dir)
    try:
        with open(TEMPLATE_INDEX_CACHE, "w", encoding="utf-8") as file_obj:
            json.dump(entries, file_obj, indent=2)
    except Exception as exc:
        logger.warning("Could not write template index cache: %s", exc)
    return entries


def load_template_index(library_dir=None):
    return refresh_template_index(library_dir=library_dir)


def get_template_library_status(library_dir=None):
    base_dir = library_dir or TEMPLATE_LIBRARY_DIR
    if not base_dir or not os.path.isdir(base_dir):
        return f"Template library not found: {base_dir}"
    entries = load_template_index(library_dir=base_dir)
    mode = "curated" if TEMPLATE_CURATED_MODE else "all"
    return f"Template library ({mode}): {len(entries)} circuits indexed from {base_dir}"


def match_template(query, entries=None, library_dir=None, min_score=0.55):
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return None

    template_entries = entries if entries is not None else load_template_index(library_dir=library_dir)
    if not template_entries:
        return None

    query_tokens = _tokenize(query)
    excluded_query_terms = []
    if TEMPLATE_CURATED_MODE:
        excluded_query_terms = [
            _normalize_text(keyword)
            for keyword in TEMPLATE_EXCLUDED_NAME_KEYWORDS
            if _normalize_text(keyword) and _normalize_text(keyword) in normalized_query
        ]
    best_match = None
    best_score = 0.0

    for entry in template_entries:
        # If a query explicitly asks for an excluded family (for example, "three-phase"),
        # avoid silently mapping to a simpler non-equivalent template in curated mode.
        if excluded_query_terms:
            entry_text = f"{entry.get('normalized_name', '')} {entry.get('normalized_relpath', '')}"
            if any(term not in entry_text for term in excluded_query_terms):
                continue

        entry_tokens = set(entry.get("tokens", []))
        token_overlap = len(query_tokens & entry_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
        name_ratio = SequenceMatcher(None, normalized_query, entry["normalized_name"]).ratio()
        rel_ratio = SequenceMatcher(None, normalized_query, entry["normalized_relpath"]).ratio()

        # Highest-priority deterministic match for exact circuit-name queries.
        if normalized_query == entry.get("normalized_name", ""):
            best_match = dict(entry)
            best_match["score"] = 1.0
            best_score = 1.0
            break

        # Strong signal when the canonical circuit name appears in the prompt text.
        contains_boost = 0.0
        entry_name = entry.get("normalized_name", "")
        entry_name_tokens = _tokenize(entry_name)
        query_token_count = max(1, len(query_tokens))
        if entry_name and entry_name in normalized_query:
            # Prefer more specific names (more matching tokens relative to query).
            contains_boost = 0.2 + 0.45 * (len(entry_name_tokens) / query_token_count)
        elif normalized_query and normalized_query in entry_name:
            contains_boost = 0.2

        # Small boost when category words are present (helps disambiguate similar circuit names).
        category_tokens = _tokenize(entry.get("category", ""))
        category_overlap = len(query_tokens & category_tokens) / max(1, len(category_tokens)) if category_tokens else 0.0
        category_boost = 0.1 * category_overlap

        score = max(name_ratio, rel_ratio) * 0.45 + token_overlap * 0.55 + contains_boost + category_boost
        score = min(score, 1.0)

        if score > best_score:
            best_score = score
            best_match = dict(entry)
            best_match["score"] = round(score, 3)

    if not best_match or best_score < min_score:
        return None
    return best_match