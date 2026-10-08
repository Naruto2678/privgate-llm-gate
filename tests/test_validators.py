from privgate.validators import luhn_check_digit, luhn_valid, pan_valid, verhoeff_check_digit, verhoeff_valid


def test_verhoeff_known_example():
    assert verhoeff_check_digit("236") == "3"  # classic textbook example
    assert verhoeff_valid("2363")
    assert not verhoeff_valid("2364")
    assert not verhoeff_valid("23a3")


def test_verhoeff_roundtrip_and_single_digit_errors_detected():
    body = "49876501234"
    number = body + verhoeff_check_digit(body)
    assert verhoeff_valid(number)
    for i in range(len(number)):  # Verhoeff catches every single-digit mistake
        wrong = number[:i] + str((int(number[i]) + 1) % 10) + number[i + 1 :]
        assert not verhoeff_valid(wrong)


def test_luhn():
    assert luhn_valid("4111111111111111")
    assert not luhn_valid("4111111111111112")
    assert not luhn_valid("411111")  # too short for a card
    body = "453201511283036"
    assert luhn_valid(body + luhn_check_digit(body))


def test_pan_holder_type():
    assert pan_valid("ABCPE1234F")  # 4th letter P = individual
    assert pan_valid("AAACR5055K")  # C = company
    assert not pan_valid("ABCXE1234F")  # X is not a holder type
