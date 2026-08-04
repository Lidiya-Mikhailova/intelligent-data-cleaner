from src.forms import detect_form, extract_form

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
