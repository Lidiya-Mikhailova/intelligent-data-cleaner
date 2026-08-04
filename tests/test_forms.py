import pytest

from src.forms import FORM_REGISTRY, detect_form, extract_form

W2_LINES = [
    "Form W-2 Wage and Tax Statement",
    "Employer identification number: 12-3456789",
    "Employer name: Acme Corp",
    "Employee name: John Doe",
    "Wages, tips other compensation: 50000",
    "Federal income tax withheld: 6200",
]


def test_detect_w2():
    assert detect_form(W2_LINES) == "w2"


def test_extract_w2_fields():
    out = extract_form(W2_LINES, "w2")
    assert not out.empty
    fields = set(out["Field"].astype(str))
    assert "ein" in fields
    assert "employer_name" in fields
    assert "federal_tax_withheld" in fields


def test_detect_unknown_returns_none():
    assert detect_form(["hello world", "no form here"]) is None


def test_registry_has_known_forms():
    assert set(FORM_REGISTRY) == {"w2", "w4", "1099"}


def test_extract_unknown_form_raises():
    with pytest.raises(ValueError, match="Unknown form type"):
        extract_form(["Form W-2"], "1120")


def test_extract_form_unmatched_lines_become_text():
    out = extract_form(["Form W-2 Wage and Tax Statement", "some random note"], "w2")
    assert "Text" in set(out["Field"].astype(str))


def test_detect_w4():
    assert detect_form(["Form W-4 Employee's Withholding Certificate"]) == "w4"


def test_extract_w4_fields():
    lines = [
        "Form W-4",
        "First name and middle initial: John",
        "Last name: Smith",
        "City or town: New York",
        "State: NY",
        "Zip code: 10001",
        "Social security number: 123-45-6789",
        "Single",
        "Dependents: 2",
        "Signature",
        "Date: 2024-01-01",
    ]
    out = extract_form(lines, "w4")
    fields = set(out["Field"].astype(str))
    assert {
        "first_name_middle_initial",
        "last_name",
        "city",
        "state",
        "zip_code",
        "ssn",
        "filing_status_single",
        "dependents",
        "signature",
        "date",
    }.issubset(fields)


def test_w4_detect_rejects_other_forms():
    assert detect_form(["Form W-2 Wage and Tax Statement"]) != "w4"


def test_detect_1099():
    assert detect_form(["Form 1099-NEC Nonemployee Compensation"]) == "1099"


def test_extract_1099_fields():
    lines = [
        "Form 1099-NEC",
        "Payer name: Acme Corp",
        "Payer address: 1 Main St",
        "Payer id number: 12-3456789",
        "Recipient name: Jane Doe",
        "Recipient address: 2 Oak Ave",
        "Recipient id number: 987-65-4321",
        "Nonemployee compensation: 40000",
        "Federal income tax withheld: 3000",
    ]
    out = extract_form(lines, "1099")
    fields = set(out["Field"].astype(str))
    assert {
        "payer_name",
        "payer_ein",
        "recipient_name",
        "recipient_tin",
        "nonemployee_comp",
        "federal_tax_withheld",
    }.issubset(fields)


def test_extract_1099_from_text_with_separator():
    lines = [
        "Tax document: 1099-MISC Miscellaneous Income",
        "Payer name: Global Corp",
    ]
    out = extract_form(lines, "1099")
    assert "payer_name" in set(out["Field"].astype(str))
