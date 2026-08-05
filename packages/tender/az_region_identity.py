"""Region-name canonicalization (TENDER_INTELLIGENCE_SPEC.md §5.3's
"граф объектов" -- object graph -- foundation, not the full graph). Pure
string matching, built only from region names actually observed in real
captured eTender buyer names
(fixtures/tender-snapshots/etender/design_tender_search_page{1,2}.raw.json)
-- not a general list of Azerbaijan's ~66 rayons typed from memory, which
would risk an unobserved region's spelling being wrong and silently
mis-normalizing text that happens to contain it.

Extending _KNOWN_REGIONS to more regions is real, easy future work once
more real buyer names are captured -- not attempted speculatively here."""

from __future__ import annotations

# Canonical name -> the token(s) that identify it inside a real
# buyerOrganizationName string (uppercase, as eTender returns them).
_KNOWN_REGIONS: dict[str, tuple[str, ...]] = {
    "Zaqatala": ("ZAQATALA",),
    "Siyəzən": ("SİYƏZƏN",),
    "Lerik": ("LERİK",),
    "Naxçıvan": ("NAXÇIVAN",),
}


def canonicalize_region(text: str) -> str | None:
    upper = text.upper()
    for canonical, tokens in _KNOWN_REGIONS.items():
        if any(token in upper for token in tokens):
            return canonical
    return None
