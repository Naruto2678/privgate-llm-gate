import pytest

from privgate.config import PrivacyConfig
from privgate.detectors import find_entities
from privgate.ner import spacy_available
from tests.conftest import make_aadhaar, make_card

CFG = PrivacyConfig()


def types(text, cfg=CFG):
    return [(e.type, e.value) for e in find_entities(text, cfg)]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("call +91 98765 43210 now", ("PHONE", "+91 98765 43210")),
        ("call 9876543210 now", ("PHONE", "9876543210")),
        ("call 98765-43210 now", ("PHONE", "98765-43210")),
        ("call 098765-43210 now", ("PHONE", "098765-43210")),
        ("mail priya.nair@gmail.com please", ("EMAIL", "priya.nair@gmail.com")),
        ("pay priya@okaxis today", ("UPI_ID", "priya@okaxis")),
        ("IFSC HDFC0001234 branch", ("IFSC", "HDFC0001234")),
        ("PAN ABCPE1234F on file", ("PAN", "ABCPE1234F")),
        ("A/C no. 50100123456789 debited", ("BANK_ACCOUNT", "50100123456789")),
        ("account number: 123456789012 closed", ("BANK_ACCOUNT", "123456789012")),
        ("Delivery PIN 302001, Jaipur", ("PIN_CODE", "302001")),
        ("pincode: 560034", ("PIN_CODE", "560034")),
        ("Mr. Rohan Mehta here", ("PERSON", "Rohan Mehta")),
        ("My name is Priya Nair and", ("PERSON", "Priya Nair")),
        ("Customer Name: Sneha Iyer", ("PERSON", "Sneha Iyer")),
    ],
)
def test_each_detector(text, expected):
    assert expected in types(text)


def test_aadhaar_with_valid_checksum_in_all_formats():
    a = make_aadhaar()
    for fmt in (a, a.replace(" ", ""), a.replace(" ", "-")):
        assert ("AADHAAR", fmt) in types(f"Aadhaar {fmt} attached")


def test_card_detected_and_not_mistaken_for_aadhaar():
    card = make_card()
    found = types(f"card {card} was charged")
    assert found == [("CREDIT_CARD", card)]  # one entity covering all 16 digits, no partial Aadhaar


def test_checksums_reject_lookalikes():
    assert types("order 987654321098 shipped") == []  # 12 digits, fails Verhoeff
    assert types("tracking 12345678901234 pending") == []  # 14 digits, fails Luhn
    assert types("product ABCXE1234F in stock") == []  # PAN shape but invalid holder letter


def test_plain_regex_baseline_does_flag_lookalikes():
    naive = PrivacyConfig(use_checksums=False, use_context_rules=False)
    kinds = {t for t, _ in types("order 987654321098 and tracking 12345678901234 and ABCXE1234F", naive)}
    assert kinds == {"AADHAAR", "CREDIT_CARD", "PAN"}


def test_context_rules_off_ignores_account_pin_and_names():
    no_ctx = PrivacyConfig(use_context_rules=False)
    # (the account number is chosen so that it does not accidentally pass the Luhn card check)
    assert types("A/C no. 50100123456780 PIN 302001 Mr. Rohan Mehta", no_ctx) == []


def test_context_beats_lookalike_number_pattern():
    # 14 digits that happen to pass Luhn must still be an account number when labelled as one
    body = "5010012345678"
    number = body + luhn_check_digit_str(body)
    assert types(f"A/C no. {number}") == [("BANK_ACCOUNT", number)]


def luhn_check_digit_str(body):
    from privgate.validators import luhn_check_digit

    return luhn_check_digit(body)


def test_uncontexted_bare_numbers_are_left_alone():
    assert types("ticket 20481, version 4.2.1, budget 25000 rupees, OTP 482913") == []


def test_names_never_span_a_line_break():
    found = types("Customer Name: Sneha Iyer\nPhone: 9876543210")
    assert ("PERSON", "Sneha Iyer") in found and ("PHONE", "9876543210") in found


def test_name_mentions_are_linked_signature_case():
    text = "My name is Priya Nair and my order is late.\nThanks,\nPriya"
    persons = [e.value for e in find_entities(text, CFG) if e.type == "PERSON"]
    assert persons == ["Priya Nair", "Priya"]


def test_full_name_repeated_stays_one_entity():
    text = "I am Priya Nair. Regards, Priya Nair"
    assert [e.value for e in find_entities(text, CFG) if e.type == "PERSON"] == ["Priya Nair", "Priya Nair"]


def test_detect_list_restricts_types():
    only_email = PrivacyConfig(detect=["EMAIL"])
    assert types("Mr. Rohan Mehta rohan@gmail.com 9876543210", only_email) == [("EMAIL", "rohan@gmail.com")]


def test_email_and_upi_do_not_collide():
    assert types("ab@gmail.com and ab@ybl") == [("EMAIL", "ab@gmail.com"), ("UPI_ID", "ab@ybl")]


def test_entities_are_sorted_and_non_overlapping():
    text = "Mr. Rohan Mehta 9876543210 rohan@gmail.com PIN 302001"
    ents = find_entities(text, CFG)
    assert all(a.end <= b.start for a, b in zip(ents, ents[1:], strict=False))


@pytest.mark.skipif(not spacy_available(), reason="spaCy model not installed")
def test_spacy_finds_bare_names():
    from privgate.ner import person_spans

    cfg = PrivacyConfig(use_spacy_ner=True)
    persons = [e.value for e in find_entities("Please contact Priya Nair at the Jaipur branch.", cfg, person_spans)]
    assert "Priya Nair" in persons
