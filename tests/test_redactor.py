import pytest

from privgate.config import PrivacyConfig
from privgate.detectors import find_entities
from privgate.errors import PrivacyLeakError
from privgate.redactor import assert_clean, mask, redact, restore

CFG = PrivacyConfig()


def do(text):
    return redact(text, find_entities(text, CFG))


def test_placeholders_and_vault():
    r = do("I am Priya Nair, call 9876543210 or mail priya@gmail.com")
    assert r.redacted_text == "I am [PERSON_1], call [PHONE_1] or mail [EMAIL_1]"
    assert r.vault == {"[PERSON_1]": "Priya Nair", "[PHONE_1]": "9876543210", "[EMAIL_1]": "priya@gmail.com"}


def test_same_value_same_placeholder_even_with_different_formatting():
    r = do("Call 98765 43210. Again: 9876543210.")
    assert r.redacted_text == "Call [PHONE_1]. Again: [PHONE_1]."
    assert len(r.vault) == 1


def test_first_name_links_to_full_name_placeholder():
    r = do("I am Priya Nair.\nThanks,\nPriya")
    assert r.redacted_text == "I am [PERSON_1].\nThanks,\n[PERSON_1]"


def test_different_people_get_different_placeholders():
    r = do("Mr. Rohan Mehta and Mrs. Sneha Iyer")
    assert r.redacted_text == "Mr. [PERSON_1] and Mrs. [PERSON_2]"


def test_restore_roundtrip_and_unknown_placeholders():
    r = do("I am Priya Nair, call 9876543210")
    out, unknown = restore("Dear [PERSON_1], we will call [PHONE_1]. Ref [ PERSON_1 ] and [EMAIL_9].", r.vault)
    assert out == "Dear Priya Nair, we will call 9876543210. Ref Priya Nair and [EMAIL_9]."
    assert unknown == ["[EMAIL_9]"]


def test_assert_clean_passes_on_redacted_and_fails_on_leak():
    r = do("call 9876543210")
    assert_clean(r.redacted_text, r.vault)
    with pytest.raises(PrivacyLeakError):
        assert_clean("please call 9876543210 now", r.vault)


def test_leak_check_is_token_aware():
    # the phone number is a prefix of a longer order number: that is NOT a leak
    assert_clean("order 987654321098 is late", {"[PHONE_1]": "9876543210"})


def test_text_without_entities_is_unchanged():
    r = do("The app crashes on version 4.2.1")
    assert r.redacted_text == "The app crashes on version 4.2.1" and r.vault == {}


def test_mask():
    assert mask("Rajesh Kumar") == "R**********r"
    assert mask("abc") == "***"
