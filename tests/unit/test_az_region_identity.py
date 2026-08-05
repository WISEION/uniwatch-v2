"""Real buyerOrganizationName values, captured 2026-08-05
(fixtures/tender-snapshots/etender/design_tender_search_page{1,2}.raw.json),
ground the region canonicalizer -- it must not guess a region for a buyer
name that doesn't actually name one."""

from __future__ import annotations

from packages.tender.az_region_identity import canonicalize_region


def test_canonicalizes_real_rayon_executive_authority_names():
    assert canonicalize_region("ZAQATALA RAYONU İCRA HAKİMİYYƏTİ.") == "Zaqatala"
    assert canonicalize_region("SİYƏZƏN RAYON İCRA HAKİMİYYƏTİ") == "Siyəzən"
    assert canonicalize_region("LERİK RAYON İCRA HAKİMİYYƏTİ") == "Lerik"
    assert canonicalize_region("NAXÇIVAN ŞƏHƏR İCRA HAKİMİYYƏTİ") == "Naxçıvan"


def test_returns_none_for_unrecognized_or_non_regional_buyers():
    assert canonicalize_region('"TİKİLMƏKDƏ OLAN OBYEKTLƏRİN MÜDİRİYYƏTİ" PUBLİK HÜQUQİ ŞƏXSİ') is None
    assert canonicalize_region("AZƏRBAYCAN RESPUBLİKASI DÖVLƏT NEFT FONDU") is None
