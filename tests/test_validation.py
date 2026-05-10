import pytest

from src.validation.models import SilverRecord


def test_valid_record():
    rec = SilverRecord(ID=1, Name="John Doe", Age=30, Email="john@example.com")
    assert rec.ID == 1
    assert rec.Name == "John Doe"
    assert rec.Age == 30


def test_valid_record_minimal():
    rec = SilverRecord(ID=1, Name="Alice")
    assert rec.Name == "Alice"
    assert rec.Age is None
    assert rec.Email is None


def test_empty_name_raises():
    with pytest.raises(ValueError, match="Name must not be empty"):
        SilverRecord(ID=1, Name="")


def test_blank_name_raises():
    with pytest.raises(ValueError, match="Name must not be empty"):
        SilverRecord(ID=1, Name="   ")


def test_empty_age_becomes_none():
    rec = SilverRecord(ID=1, Name="Anna", Age="")
    assert rec.Age is None


def test_negative_age_raises():
    with pytest.raises(ValueError, match="Age must be between 0 and 150"):
        SilverRecord(ID=1, Name="Test", Age=-5)


def test_age_over_150_raises():
    with pytest.raises(ValueError, match="Age must be between 0 and 150"):
        SilverRecord(ID=1, Name="Test", Age=200)


def test_age_999_raises():
    with pytest.raises(ValueError, match="Age must be between 0 and 150"):
        SilverRecord(ID=1, Name="Test", Age=999)


def test_age_zero_is_valid():
    rec = SilverRecord(ID=1, Name="Baby", Age=0)
    assert rec.Age == 0


def test_valid_email():
    rec = SilverRecord(ID=1, Name="John", Email="john@example.com")
    assert rec.Email == "john@example.com"


def test_idn_email_valid():
    rec = SilverRecord(ID=1, Name="User", Email="user@тест.рф")
    assert rec.Email == "user@тест.рф"


def test_idn_email_cyrillic():
    rec = SilverRecord(ID=1, Name="User", Email="error@тест.рф")
    assert rec.Email == "error@тест.рф"


def test_invalid_email_no_at():
    with pytest.raises(ValueError, match="Invalid email format"):
        SilverRecord(ID=1, Name="Test", Email="not-an-email")


def test_invalid_email_no_tld():
    with pytest.raises(ValueError, match="Invalid email format"):
        SilverRecord(ID=1, Name="Test", Email="lisi@invalid")


def test_empty_email_becomes_none():
    rec = SilverRecord(ID=1, Name="Test", Email="")
    assert rec.Email is None


def test_none_email():
    rec = SilverRecord(ID=1, Name="Test", Email=None)
    assert rec.Email is None


def test_empty_address_becomes_none():
    rec = SilverRecord(ID=1, Name="Test", Address="")
    assert rec.Address is None


def test_empty_notes_becomes_none():
    rec = SilverRecord(ID=1, Name="Test", Notes="")
    assert rec.Notes is None


def test_name_stripped():
    rec = SilverRecord(ID=1, Name="  Padded  ")
    assert rec.Name == "Padded"


def test_multiple_empty_fields():
    rec = SilverRecord(ID=1, Name="User33", Age="", Email="", Address="", Notes="")
    assert rec.Age is None
    assert rec.Email is None
    assert rec.Address is None
    assert rec.Notes is None
