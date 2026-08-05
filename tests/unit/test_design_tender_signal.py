"""Real eventNames captured 2026-08-05
(fixtures/tender-snapshots/etender/design_tender_search_page{1,2}.raw.json)
ground both the true positives and the real false positives the
design-tender classifier must get right."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.design_tender_signal import build_design_tender_signal, classify_design_tender

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"

# Ground truth for every real item across both frozen fixture pages
# (fixtures/tender-snapshots/etender/MANIFEST.md), verified by hand against
# the actual Azerbaijani text before this classifier was written.
_PAGE1_EXPECTED_TRUE_EVENT_IDS = {
    356515,
    356470,
    356459,
    356458,
    356453,
    356430,
    356426,
    356418,
    356406,
    356386,
}
_PAGE2_EXPECTED_TRUE_EVENT_IDS = {356192, 356143, 356140, 356055, 356039, 355972}
_PAGE2_EXPECTED_FALSE_EVENT_IDS = {356291, 356048, 356027, 355959}


def test_classifier_matches_every_real_item_across_both_fixture_pages():
    page1 = json.loads((FIXTURES / "design_tender_search_page1.raw.json").read_bytes())
    page2 = json.loads((FIXTURES / "design_tender_search_page2.raw.json").read_bytes())

    page1_true = {item["eventId"] for item in page1["items"] if classify_design_tender(item["eventName"])}
    assert page1_true == _PAGE1_EXPECTED_TRUE_EVENT_IDS

    page2_true = {item["eventId"] for item in page2["items"] if classify_design_tender(item["eventName"])}
    page2_false = {item["eventId"] for item in page2["items"] if not classify_design_tender(item["eventName"])}
    assert page2_true == _PAGE2_EXPECTED_TRUE_EVENT_IDS
    assert page2_false == _PAGE2_EXPECTED_FALSE_EVENT_IDS


def test_classifies_real_design_estimate_tenders_as_true():
    assert classify_design_tender(
        "Ceyranbatan-Abşeron-Balaxanı-Ramana-Zirə-Pirallahı magistral su kəməri və trassa boyunca "
        "yerləşən mərkəzi su anbarların tikintisi çərçivəsində layihə-smeta sənədlərinin hazırlanması"
    )
    assert classify_design_tender("Layihə-smeta sənədlərinin hazırlanması xidmətlərinin satınalınması")
    # Real space-separated variant (no hyphen), event 356430, page 1.
    assert classify_design_tender(
        "Nizami küçəsində yerləşən bağda abadlıq işləri ilə əlaqədar layihə smeta sənədlərinin hazırlanması"
    )
    # Real typo variant found in the wild, event 356453, page 1: "layihələmdirilməsi"
    # (should be "layihələndirilməsi").
    assert classify_design_tender(
        "Yanğın əleyhinə sulusöndürmə sisteminin quraşdırılmasının layihələmdirilməsi xidmətlərinin satın alınması"
    )
    # Correct spelling of the same verb stem, event 356470, page 1.
    assert classify_design_tender(
        "DOST Rəqəmsal Media Studiyasının inzibati binasının əsaslı təmir işləri üzrə "
        "layihələndirilməsi xidmətlərinin satın alınması"
    )
    # Bare verb, no "smeta", event 356039, page 2.
    assert classify_design_tender("Artezian quyularının layihələndirilməsi")


def test_rejects_real_false_positives_using_layihe_as_generic_project():
    # Real eventNames, page 2 (events 356291/356027) -- "layihələr-" is the PLURAL NOUN
    # "projects" (layihələ + r), sharing its first 8 characters with the design-VERB stem
    # "layihələn-"/"layihələm-" but diverging at the 9th -- must not classify as design/TEO.
    assert not classify_design_tender(
        "Layihələrin idarə olunması, Fərdi uçota nəzarət və Sosial sığorta departamentləri, "
        "habelə SÖTMF üçün Ofis sahəsinin və binanın daxilində Arxiv sahəsinin icarəsi "
        "xidmətlərinin satın alınması"
    )
    assert not classify_design_tender(
        "Təşviqat xarakterli tədbirlərin və layihələrin təşkili ilə bağlı xidmətlərin satın alınması"
    )
    # Real true negatives for different reasons -- neither shares the design-verb stem at all.
    assert not classify_design_tender("GPON layihəsi üzrə Bras, Olt ,Ont və digər avadanlıqlarının satınalınması")
    assert not classify_design_tender(
        "FHN TTNDA S.Ə.Dadaşov adına Elmi-Tətqiqat və Layihə-Konstruktor İnşaat Materialları "
        "İnstitutu üçün Daşınma (evakuator) xidmətlərinin satınalınması"
    )


def test_build_design_tender_signal_from_real_open_tender():
    item = {
        "eventId": 356515,
        "eventName": (
            "Ceyranbatan-Abşeron-Balaxanı-Ramana-Zirə-Pirallahı magistral su kəməri layihə-smeta sənədlərinin hazırlanması"
        ),
        "buyerOrganizationName": "AZƏRSU ASC",
        "publishDate": 1735689600000,
        "awardedParticipantName": None,
        "documentViewType": 1,
    }
    signal = build_design_tender_signal(
        item, raw_snapshot_id=99, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-design-1"
    )
    assert signal.signal_type == "design_tender"
    assert signal.source == "etender"
    assert signal.raw_snapshot_id == 99
    assert signal.value["event_id"] == 356515
    assert signal.value["is_awarded"] is False
    assert signal.ttl_class == "design_phase_tender"
    assert signal.confidence == "official_source"
    assert signal.object_customer == "AZƏRSU ASC"
    assert signal.object_region is None
    assert signal.object_project_type is None


def test_build_design_tender_signal_marks_awarded_when_participant_present():
    item = {
        "eventId": 111222,
        "eventName": "Test layihə-smeta sənədlərinin hazırlanması",
        "buyerOrganizationName": "TEST QURUM",
        "publishDate": 1735689600000,
        "awardedParticipantName": "SOME AWARDED VENDOR MMC",
        "documentViewType": 1,
    }
    signal = build_design_tender_signal(
        item, raw_snapshot_id=100, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-design-2"
    )
    assert signal.value["is_awarded"] is True
    assert signal.value["awarded_participant_name"] == "SOME AWARDED VENDOR MMC"
