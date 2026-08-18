"""
search_engine.py
================
Loads material databases from the catalog (material_catalog.json) and
provides category-wise listing and full-text search across one or
more regional SOR files.

Schema (v2)
-----------
Sections are grouped by sheetName only.  "type" is gone; "component" on
each entry is the sole authority (plain str for single, list for multi).

Key public API
--------------
engine = MaterialSearchEngine()                       # all OK databases
engine = MaterialSearchEngine(region="Bihar")         # filter by region
engine = MaterialSearchEngine(db_keys=["INDIA/Bihar/Darbhanga-2025"])

engine.list_categories()                              # { db_key: { sheet: [components] } }
engine.list_components()                              # flat sorted list of all components
engine.list_components(category="Foundation")         # components in one sheet
engine.list_by_category("Foundation")                 # all entries in sheet
engine.list_by_category("Foundation", component="Pile")  # further filter by component
engine.search("steel rebar")                          # full-text across all
engine.search("steel rebar", category="Sub Structure", component="Pier")
engine.search("PVC", region="Bihar")
engine.search_advanced("steel rebar")                 # same matching, but also checks 'description'
engine.list_tokens()                                  # vocabulary of searchable tokens
engine.list_tokens(category="Foundation", region="Bihar")
"""

import json
import re
from three_ps_lcca_gui.gui.components.structure.registry.material_catalog import (
    get_registry, get_path, list_databases,
)
from three_ps_lcca_gui.gui.components.structure.registry.tokenizer import (
    tokenize_name as _tokenize_name,
)


# ─────────────────────────────────────────────────────────────────────────────
#  LOW-LEVEL TEXT UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

class AdvancedSearchEngine:
    @staticmethod
    def normalize(text: str) -> str:
        """Lowercase, strip special chars, collapse spaces."""
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'[(),\-/]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Split normalized text into word tokens."""
        normalized = AdvancedSearchEngine.normalize(text)
        return normalized.split() if normalized else []

    @staticmethod
    def tokenize_name(text: str) -> list[str]:
        """Stop-word-filtered tokens for a material name/description, as
        used to build the registry's `.tokens` sidecars (tokenizer.py)."""
        return _tokenize_name(text)

    @staticmethod
    def _token_matches(tok: str, item: str) -> bool:
        """
        Check if a single query token matches within the item text.
        Handles direct substring and concatenated units (e.g. "500mm").
        """
        tok  = AdvancedSearchEngine.normalize(tok)
        item = AdvancedSearchEngine.normalize(item)
        if tok in item:
            return True
        parts = re.findall(r'[a-z]+|\d+', tok)
        if len(parts) > 1:
            return all(p in item for p in parts)
        return False

    @staticmethod
    def is_match(query: str, item_name: str) -> bool:
        """
        True if every query token appears somewhere in the item name.
        Order-independent, partial-word and concatenated-unit aware.
        """
        tokens          = AdvancedSearchEngine.tokenize(query)
        normalized_item = AdvancedSearchEngine.normalize(item_name)
        return all(
            AdvancedSearchEngine._token_matches(tok, normalized_item)
            for tok in tokens
        )


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _component_matches(component_val, query: str) -> bool:
    """Case-insensitive check whether query matches any component on the entry."""
    if not component_val:
        return False
    q = query.lower()
    if isinstance(component_val, list):
        return any(q == c.lower() for c in component_val)
    return q == str(component_val).lower()


def _component_list(component_val) -> list[str]:
    """Normalise a component value (str or list) to a flat list of strings."""
    if isinstance(component_val, list):
        return component_val
    if component_val:
        return [component_val]
    return []


# ─────────────────────────────────────────────────────────────────────────────
#  MATERIAL SEARCH ENGINE  (registry-aware)
# ─────────────────────────────────────────────────────────────────────────────

class MaterialSearchEngine:
    """
    Loads validated SOR databases from the registry and exposes
    category-wise listing and full-text search.

    Parameters
    ----------
    db_keys   : explicit list of db_keys to load; if None loads all OK dbs
    country   : filter by country folder name (e.g. "INDIA")
    region    : filter by region sub-folder  (e.g. "Bihar")
    sheet     : only load databases that contain this sheetName
    component : only load databases that contain this component
    """

    def __init__(self,
                 db_keys:   list[str] | None = None,
                 country:   str | None = None,
                 region:    str | None = None,
                 sheet:     str | None = None,
                 component: str | None = None):

        self._registry = get_registry()
        self._data: dict[str, list[dict]] = {}   # db_key → raw JSON (list of sections)

        if db_keys:
            keys_to_load = [k for k in db_keys if k in self._registry]
        else:
            entries      = list_databases(country=country, region=region,
                                          sheet=sheet, component=component)
            keys_to_load = [e["db_key"] for e in entries if e["status"] == "OK"]

        for key in keys_to_load:
            try:
                path = get_path(key)
                with open(path, "r", encoding="utf-8") as f:
                    self._data[key] = json.load(f)
            except Exception as e:
                print(f"[search_engine] Skipping '{key}': {e}")

        if not self._data:
            print("[search_engine] Warning: no databases loaded.")

    # ── internal helpers ───────────────────────────────────────────────────

    def _iter_items(self,
                    db_key:    str | None = None,
                    category:  str | None = None,
                    component: str | None = None):
        """
        Yield every entry across loaded databases, enriched with:
          db_key, region, category (sheetName), country.

        Filters:
          category  — restrict to sheetName (case-insensitive)
          component — restrict to entries whose component matches
                      (case-insensitive, handles str and list)
        """
        registry = self._registry
        sources  = {db_key: self._data[db_key]} if db_key else self._data

        for key, sections in sources.items():
            meta    = registry.get(key, {})
            region  = meta.get("region", "")
            country = meta.get("country", "")

            for section in sections:
                sheet = section.get("sheetName", "")

                if category and sheet.lower() != category.lower():
                    continue

                for entry in section.get("data", []):
                    if component and not _component_matches(entry.get("component"), component):
                        continue

                    yield {
                        "db_key":   key,
                        "region":   region,
                        "country":  country,
                        "category": sheet,
                        **entry,
                    }

    # ── PUBLIC API ─────────────────────────────────────────────────────────

    def loaded_databases(self) -> list[str]:
        """Return list of currently loaded db_keys."""
        return list(self._data.keys())

    def list_categories(self) -> dict[str, dict[str, list[str]]]:
        """
        Return all available categories and their components, grouped by db_key.

        Returns
        -------
        { db_key: { sheetName: [component, ...] } }
        """
        result: dict[str, dict[str, list[str]]] = {}
        for key, sections in self._data.items():
            cat_map: dict[str, list[str]] = {}
            for section in sections:
                sheet = section.get("sheetName", "")
                cat_map.setdefault(sheet, [])
                seen = set(cat_map[sheet])
                for entry in section.get("data", []):
                    for comp in _component_list(entry.get("component")):
                        if comp and comp not in seen:
                            cat_map[sheet].append(comp)
                            seen.add(comp)
            result[key] = cat_map
        return result

    def list_components(self, category: str | None = None) -> list[str]:
        """
        Return a sorted list of all unique component values across loaded databases,
        optionally restricted to a sheetName category.
        """
        seen: set[str] = set()
        for key, sections in self._data.items():
            for section in sections:
                if category and section.get("sheetName", "").lower() != category.lower():
                    continue
                for entry in section.get("data", []):
                    for comp in _component_list(entry.get("component")):
                        if comp:
                            seen.add(comp)
        return sorted(seen)

    def list_sheet_components(self) -> list[tuple[str, str]]:
        """
        Return sorted [(component, sheetName), ...] for every unique
        (component, sheet) pair across loaded databases.
        """
        seen: set[tuple[str, str]] = set()
        result: list[tuple[str, str]] = []
        for sections in self._data.values():
            for section in sections:
                sheet = section.get("sheetName", "")
                for entry in section.get("data", []):
                    for comp in _component_list(entry.get("component")):
                        if comp:
                            pair = (comp, sheet)
                            if pair not in seen:
                                seen.add(pair)
                                result.append(pair)
        return sorted(result, key=lambda p: (p[0].lower(), p[1].lower()))

    def list_by_category(self,
                         category:  str,
                         component: str | None = None,
                         db_key:    str | None = None) -> list[dict]:
        """
        Return all entries in a given category (sheetName),
        optionally filtered by component and / or db_key.

        Parameters
        ----------
        category  : e.g. "Foundation", "Super Structure"
        component : e.g. "Pile", "Pier"  (optional)
        db_key    : restrict to one database (optional)
        """
        return list(self._iter_items(db_key=db_key,
                                     category=category,
                                     component=component))

    def search(self,
               query:     str,
               category:  str | None = None,
               component: str | None = None,
               db_key:    str | None = None,
               region:    str | None = None) -> list[dict]:
        """
        Full-text search across material names.

        Parameters
        ----------
        query     : tokens to match against entry 'name'
        category  : restrict to sheetName            (optional)
        component : restrict to component value       (optional)
        db_key    : restrict to one db_key            (optional)
        region    : restrict to a region              (optional)
        """
        results = []
        for item in self._iter_items(db_key=db_key,
                                     category=category,
                                     component=component):
            if region and item.get("region", "").lower() != region.lower():
                continue
            if AdvancedSearchEngine.is_match(query, item.get("name", "")):
                results.append(item)
        return results

    def search_advanced(self,
                        query:     str,
                        category:  str | None = None,
                        component: str | None = None,
                        db_key:    str | None = None,
                        region:    str | None = None) -> list[dict]:
        """
        Like search(), but matches against src_id + name + description
        concatenated - so a query term that only appears in an entry's
        description or src_id (not its name) still matches, unlike search()
        which is name-only. Useful since list_tokens() draws its vocabulary
        from name + description too.

        Parameters
        ----------
        query     : tokens to match against entry 'src_id' + 'name' + 'description'
        category  : restrict to sheetName            (optional)
        component : restrict to component value       (optional)
        db_key    : restrict to one db_key            (optional)
        region    : restrict to a region              (optional)
        """
        results = []
        for item in self._iter_items(db_key=db_key,
                                     category=category,
                                     component=component):
            if region and item.get("region", "").lower() != region.lower():
                continue
            parts = [str(item["src_id"])] if item.get("src_id") else []
            parts.append(item.get("name", ""))
            if item.get("description"):
                parts.append(item["description"])
            text = " ".join(parts)
            if AdvancedSearchEngine.is_match(query, text):
                results.append(item)
        return results

    def list_tokens(self,
                    category:  str | None = None,
                    component: str | None = None,
                    db_key:    str | None = None,
                    region:    str | None = None) -> list[str]:
        """
        Return the sorted, deduplicated vocabulary of searchable tokens across
        matching entries' name/description fields - the same stop-word-filtered
        tokenizer used to build the registry's `.tokens` sidecars (tokenizer.py).
        Lets a caller (e.g. an LLM driving the search API) discover real terms
        for a database instead of guessing words that return zero results.

        Parameters
        ----------
        category  : restrict to sheetName            (optional)
        component : restrict to component value       (optional)
        db_key    : restrict to one db_key            (optional)
        region    : restrict to a region              (optional)
        """
        found: set[str] = set()
        for item in self._iter_items(db_key=db_key, category=category, component=component):
            if region and item.get("region", "").lower() != region.lower():
                continue
            found.update(AdvancedSearchEngine.tokenize_name(item.get("name", "")))
            description = item.get("description")
            if description:
                found.update(AdvancedSearchEngine.tokenize_name(description))
        return sorted(found)

    def summary(self) -> None:
        """Print a human-readable category/component summary of loaded databases."""
        cats = self.list_categories()
        print("\n" + "=" * 64)
        print("  MATERIAL DATABASE - CATEGORY SUMMARY")
        print("=" * 64)
        for db_key, cat_map in cats.items():
            meta   = self._registry.get(db_key, {})
            region = meta.get("region", "?")
            print(f"\n  [{db_key}]  ({region})")
            print(f"  {'CATEGORY':<25} COMPONENTS")
            print("  " + "-" * 55)
            for sheet, components in sorted(cat_map.items()):
                comp_str = ", ".join(components)
                print(f"  {sheet:<25} {comp_str}")


# ─────────────────────────────────────────────────────────────────────────────
#  CLI demo  - python search_engine.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = MaterialSearchEngine()
    engine.summary()

    print("\n" + "=" * 64)
    print("  CATEGORY LISTING - Foundation / Pile")
    print("=" * 64)
    items = engine.list_by_category("Foundation", component="Pile")
    for it in items[:5]:
        print(f"  [{it['db_key']}] {it['category']} | {it['component']} | "
              f"{it['name']:<40} {it['unit']:6} {it['rate']}")

    print("\n" + "=" * 64)
    print("  SEARCH - 'steel rebar'")
    print("=" * 64)
    results = engine.search("steel rebar")
    for r in results[:5]:
        comp = r.get("component")
        comp_str = ", ".join(comp) if isinstance(comp, list) else str(comp)
        print(f"  [{r['db_key']}] {r['category']:15} | {comp_str:20} | "
              f"{r['name']:<35} {r['rate']}")
