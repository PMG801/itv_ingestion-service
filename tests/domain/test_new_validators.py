"""Tests for new validation rules: email, province, coordinates, contact, postal code."""

import pytest

from domain.itv_stations.rules import ITVValidationRules, SPANISH_PROVINCES, PROVINCE_COORDS_RANGE
from domain.itv_stations.schemas import NormalizedStation
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer
from domain.itv_stations.transformers.valencia import ValenciaTransformer
from domain.itv_stations.transformers.galicia import GaliciaTransformer


# ============================================================================
# EMAIL VALIDATION TESTS
# ============================================================================

class TestEmailValidation:
    """Test email validation with simple regex."""

    def test_email_simple_valid(self) -> None:
        """Test that simple valid email passes."""
        assert ITVValidationRules.validate_email_simple("user@example.com") is True
        assert ITVValidationRules.validate_email_simple("info@itvbarcelona.cat") is True
        assert ITVValidationRules.validate_email_simple("test.user@domain.co.uk") is True

    def test_email_missing_domain(self) -> None:
        """Test that email without domain fails."""
        assert ITVValidationRules.validate_email_simple("user@") is False
        assert ITVValidationRules.validate_email_simple("user") is False

    def test_email_missing_at(self) -> None:
        """Test that email without @ fails."""
        assert ITVValidationRules.validate_email_simple("userdomain.com") is False

    def test_email_no_extension(self) -> None:
        """Test that email without top-level domain fails."""
        assert ITVValidationRules.validate_email_simple("user@domain") is False

    def test_email_none_value(self) -> None:
        """Test that None email is invalid."""
        assert ITVValidationRules.validate_email_simple(None) is False

    def test_email_empty_string(self) -> None:
        """Test that empty email is invalid."""
        assert ITVValidationRules.validate_email_simple("") is False

    def test_email_with_spaces(self) -> None:
        """Test that email with spaces is invalid."""
        assert ITVValidationRules.validate_email_simple("user @example.com") is False


# ============================================================================
# PROVINCE VALIDATION TESTS
# ============================================================================

class TestProvinceValidation:
    """Test province validation against official Spanish provinces list."""

    def test_province_valid_uppercase(self) -> None:
        """Test valid provinces in uppercase."""
        assert ITVValidationRules.validate_province_spain("BARCELONA") is True
        assert ITVValidationRules.validate_province_spain("VALENCIA") is True
        assert ITVValidationRules.validate_province_spain("MADRID") is True

    def test_province_valid_lowercase(self) -> None:
        """Test valid provinces in lowercase."""
        assert ITVValidationRules.validate_province_spain("barcelona") is True
        assert ITVValidationRules.validate_province_spain("valencia") is True

    def test_province_valid_mixed_case(self) -> None:
        """Test valid provinces in mixed case."""
        assert ITVValidationRules.validate_province_spain("Barcelona") is True
        assert ITVValidationRules.validate_province_spain("MADRID") is True

    def test_province_invalid(self) -> None:
        """Test invalid province names."""
        assert ITVValidationRules.validate_province_spain("InvalidProvince") is False
        assert ITVValidationRules.validate_province_spain("NARNIA") is False

    def test_province_with_accents(self) -> None:
        """Test provinces with accents."""
        assert ITVValidationRules.validate_province_spain("ÁLAVA") is True
        assert ITVValidationRules.validate_province_spain("ÁVILA") is True

    def test_province_none(self) -> None:
        """Test that None province is invalid."""
        assert ITVValidationRules.validate_province_spain(None) is False

    def test_province_empty_string(self) -> None:
        """Test that empty province is invalid."""
        assert ITVValidationRules.validate_province_spain("") is False

    def test_all_spanish_provinces_valid(self) -> None:
        """Test that all official Spanish provinces are valid."""
        for province in SPANISH_PROVINCES:
            assert ITVValidationRules.validate_province_spain(province) is True


# ============================================================================
# COORDINATES BY PROVINCE VALIDATION TESTS
# ============================================================================

class TestCoordinatesByProvinceValidation:
    """Test coordinate validation by province bounds."""

    def test_coords_barcelona_valid(self) -> None:
        """Test valid coordinates within Barcelona bounds."""
        # Barcelona center approximately 41.3, 2.1
        assert (
            ITVValidationRules.validate_coordinates_by_province(41.3, 2.1, "BARCELONA")
            is True
        )

    def test_coords_barcelona_invalid_too_far_north(self) -> None:
        """Test invalid coordinates north of Barcelona."""
        assert (
            ITVValidationRules.validate_coordinates_by_province(43.5, 2.1, "BARCELONA")
            is False
        )

    def test_coords_valencia_valid(self) -> None:
        """Test valid coordinates within Valencia bounds."""
        # Valencia center approximately 39.4, -0.3
        assert (
            ITVValidationRules.validate_coordinates_by_province(39.4, -0.3, "VALENCIA")
            is True
        )

    def test_coords_valencia_invalid_too_far_south(self) -> None:
        """Test invalid coordinates south of Valencia."""
        assert (
            ITVValidationRules.validate_coordinates_by_province(37.0, -0.3, "VALENCIA")
            is False
        )

    def test_coords_missing_latitude(self) -> None:
        """Test that missing latitude is invalid."""
        assert (
            ITVValidationRules.validate_coordinates_by_province(None, 2.1, "BARCELONA")
            is False
        )

    def test_coords_missing_longitude(self) -> None:
        """Test that missing longitude is invalid."""
        assert (
            ITVValidationRules.validate_coordinates_by_province(41.3, None, "BARCELONA")
            is False
        )

    def test_coords_missing_province(self) -> None:
        """Test that missing province falls back to Spain bounds check."""
        assert (
            ITVValidationRules.validate_coordinates_by_province(41.3, 2.1, None)
            is False
        )

    def test_coords_unknown_province_falls_back_to_spain(self) -> None:
        """Test that unknown province falls back to general Spain bounds."""
        # Within general Spain bounds: lat 36-43.8, lon -9.3 to 4.3
        assert (
            ITVValidationRules.validate_coordinates_by_province(41.0, 2.0, "UNKNOWNPROV")
            is True
        )


# ============================================================================
# POSTAL CODE BY PROVINCE VALIDATION TESTS
# ============================================================================

class TestPostalCodeByProvinceValidation:
    """Test postal code validation against province prefix."""

    def test_postal_code_barcelona_valid(self) -> None:
        """Test valid postal code for Barcelona (08xxx)."""
        assert (
            ITVValidationRules.validate_postal_code_by_province("08025", "BARCELONA")
            is True
        )

    def test_postal_code_barcelona_invalid(self) -> None:
        """Test invalid postal code for Barcelona (should be 08xxx)."""
        assert (
            ITVValidationRules.validate_postal_code_by_province("28001", "BARCELONA")
            is False
        )

    def test_postal_code_madrid_valid(self) -> None:
        """Test valid postal code for Madrid (28xxx)."""
        assert (
            ITVValidationRules.validate_postal_code_by_province("28001", "MADRID")
            is True
        )

    def test_postal_code_valencia_valid(self) -> None:
        """Test valid postal code for Valencia (46xxx)."""
        assert (
            ITVValidationRules.validate_postal_code_by_province("46015", "VALENCIA")
            is True
        )

    def test_postal_code_missing(self) -> None:
        """Test that missing postal code is invalid."""
        assert (
            ITVValidationRules.validate_postal_code_by_province(None, "BARCELONA")
            is False
        )

    def test_postal_code_unknown_province_allows(self) -> None:
        """Test that unknown province allows any postal code."""
        assert (
            ITVValidationRules.validate_postal_code_by_province("12345", "UNKNOWNPROV")
            is True
        )

    def test_postal_code_wrong_length(self) -> None:
        """Test that postal code with wrong length is invalid."""
        assert (
            ITVValidationRules.validate_postal_code_by_province("040", "BARCELONA")
            is False
        )


# ============================================================================
# CONTACT MINIMUM VALIDATION TESTS
# ============================================================================

class TestContactMinimumValidation:
    """Test minimum contact and location requirements."""

    def test_contact_with_phone_and_location(self) -> None:
        """Test valid contact with phone and complete location."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone="+34932123456",
                email=None,
                address="Carrer de la Industria 123",
                city="BARCELONA",
                province="BARCELONA",
                postal_code="08025",
            )
            is True
        )

    def test_contact_with_email_and_location(self) -> None:
        """Test valid contact with email and complete location."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone=None,
                email="info@itv.cat",
                address="Carrer de la Industria 123",
                city="BARCELONA",
                province="BARCELONA",
                postal_code="08025",
            )
            is True
        )

    def test_contact_with_phone_and_email(self) -> None:
        """Test valid contact with both phone and email."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone="+34932123456",
                email="info@itv.cat",
                address="Carrer de la Industria 123",
                city="BARCELONA",
                province="BARCELONA",
                postal_code="08025",
            )
            is True
        )

    def test_contact_missing_phone_and_email(self) -> None:
        """Test invalid contact without phone or email."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone=None,
                email=None,
                address="Carrer de la Industria 123",
                city="BARCELONA",
                province="BARCELONA",
                postal_code="08025",
            )
            is False
        )

    def test_contact_missing_address(self) -> None:
        """Test invalid contact without address."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone="+34932123456",
                email=None,
                address=None,
                city="BARCELONA",
                province="BARCELONA",
                postal_code="08025",
            )
            is False
        )

    def test_contact_missing_city(self) -> None:
        """Test invalid contact without city."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone="+34932123456",
                email=None,
                address="Carrer de la Industria 123",
                city=None,
                province="BARCELONA",
                postal_code="08025",
            )
            is False
        )

    def test_contact_missing_province(self) -> None:
        """Test invalid contact without province."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone="+34932123456",
                email=None,
                address="Carrer de la Industria 123",
                city="BARCELONA",
                province=None,
                postal_code="08025",
            )
            is False
        )

    def test_contact_missing_postal_code(self) -> None:
        """Test invalid contact without postal code."""
        assert (
            ITVValidationRules.validate_contact_minimum(
                phone="+34932123456",
                email=None,
                address="Carrer de la Industria 123",
                city="BARCELONA",
                province="BARCELONA",
                postal_code=None,
            )
            is False
        )


# ============================================================================
# INTEG RATION TESTS: TRANSFORMER VALIDATION
# ============================================================================

class TestTransformerValidation:
    """Test that transformers apply validation rules."""

    def test_transformer_rejects_station_invalid_email(self) -> None:
        """Test that transformer rejects station with invalid email."""
        transformer = CatalunyaTransformer()
        
        invalid_station_data = {
            "id": "TEST-001",
            "nom": "ITV Test",
            "adreca": "Carrer test 123",
            "ciutat": "Barcelona",
            "provincia": "Barcelona",
            "codi_postal": "08025",
            "latitud": 41.3,
            "longitud": 2.1,
            "telefon": "932123456",
            "email": "invalid-email-format",
        }
        
        result = transformer.transform([invalid_station_data])
        
        assert len(result) == 0
        assert len(transformer.rejected_items) == 1
        assert transformer.rejected_items[0]["reason"] == "invalid_email_format"

    def test_transformer_rejects_station_invalid_province(self) -> None:
        """Test that transformer rejects station with invalid province."""
        transformer = ValenciaTransformer()
        
        invalid_station = {
            "codigo": "VAL-001",
            "nombre": "ITV Test",
            "direccion": "Calle test 123",
            "poblacion": "Valencia",
            "provincia": "INVALIDPROVINCE",
            "codigo_postal": "46015",
            "latitud": 39.4,
            "longitud": -0.3,
            "telefono": "963456789",
            "correo": "info@test.es",
        }
        
        result = transformer.transform({"estaciones": [invalid_station]})
        
        assert len(result) == 0
        assert len(transformer.rejected_items) == 1
        assert transformer.rejected_items[0]["reason"] == "invalid_province"

    def test_transformer_rejects_station_insufficient_contact(self) -> None:
        """Test that transformer rejects station without contact info."""
        transformer = GaliciaTransformer()
        
        no_contact_station = {
            "id": "GAL-001",
            "nome": "ITV Test",
            "enderezo": "Rúa test 123",
            "concello": "Lugo",
            "provincia": "Lugo",
            "cp": "27001",
            "lat": 43.0,
            "lon": -7.5,
            "telefono": None,
            "email": None,
        }
        
        result = transformer.transform([no_contact_station])
        
        assert len(result) == 0
        assert len(transformer.rejected_items) == 1
        assert transformer.rejected_items[0]["reason"] == "insufficient_contact_or_location"

    def test_transformer_accepts_station_valid_all(self) -> None:
        """Test that transformer accepts completely valid station."""
        transformer = CatalunyaTransformer()
        
        valid_station = {
            "id": "CAT-001",
            "nom": "ITV Barcelona Test",
            "adreca": "Carrer de la Industria 123",
            "ciutat": "Barcelona",
            "provincia": "Barcelona",
            "codi_postal": "08025",
            "latitud": 41.3851,
            "longitud": 2.1734,
            "telefon": "932123456",
            "email": "info@itvbarcelona.cat",
        }
        
        result = transformer.transform([valid_station])
        
        assert len(result) == 1
        assert result[0].station_id == "CAT_CAT-001"
        assert result[0].name == "ITV Barcelona Test"


# ============================================================================
# DEDUPLICATION TESTS
# ============================================================================

class TestDuplicateWithinMessageDetection:
    """Test duplicate detection within a message."""

    def test_duplicate_id_within_message(self) -> None:
        """Test detection of duplicate station IDs."""
        transformer = CatalunyaTransformer()
        
        stations = [
            {
                "id": "DUP-001",
                "nom": "ITV Station A",
                "adreca": "Carrer A 1",
                "ciutat": "Barcelona",
                "provincia": "Barcelona",
                "codi_postal": "08025",
                "latitud": 41.3,
                "longitud": 2.1,
                "telefon": "932111111",
                "email": "a@test.es",
            },
            {
                "id": "DUP-001",  # DUPLICATE ID
                "nom": "ITV Station B",
                "adreca": "Carrer B 2",
                "ciutat": "Barcelona",
                "provincia": "Barcelona",
                "codi_postal": "08025",
                "latitud": 41.32,
                "longitud": 2.12,
                "telefono": "932222222",
                "email": "b@test.es",
            },
        ]
        
        result = transformer.transform(stations)
        
        # Only one station should be kept
        assert len(result) == 1
        # One rejection recorded for duplicate
        assert any(
            r["reason"] == "duplicate_id_within_message"
            for r in transformer.rejected_items
        )

    def test_duplicate_name_city_within_message(self) -> None:
        """Test detection of duplicate name+city combinations."""
        transformer = ValenciaTransformer()
        
        stations = [
            {
                "codigo": "VAL-001",
                "nombre": "ITV Valencia Centro",
                "direccion": "Calle A 1",
                "poblacion": "Valencia",
                "provincia": "Valencia",
                "codigo_postal": "46015",
                "latitud": 39.4,
                "longitud": -0.3,
                "telefono": "963111111",
                "correo": "a@test.es",
            },
            {
                "codigo": "VAL-002",
                "nombre": "ITV Valencia Centro",  # SAME NAME
                "direccion": "Calle B 2",
                "poblacion": "Valencia",  # SAME CITY
                "provincia": "Valencia",
                "codigo_postal": "46015",
                "latitud": 39.41,
                "longitud": -0.31,
                "telefono": "963222222",
                "correo": "b@test.es",
            },
        ]
        
        result = transformer.transform({"estaciones": stations})
        
        # Only one station should be kept
        assert len(result) == 1
        # One rejection for duplicate name+city
        assert any(
            r["reason"] == "duplicate_name_city_within_message"
            for r in transformer.rejected_items
        )


class TestDuplicateContactFieldsDetection:
    """Test duplicate contact information detection."""

    def test_duplicate_phone_within_message(self) -> None:
        """Test detection of duplicate phone numbers."""
        transformer = GaliciaTransformer()
        
        stations = [
            {
                "id": "GAL-001",
                "nome": "ITV Lugo A",
                "enderezo": "Rúa A 1",
                "concello": "Lugo",
                "provincia": "Lugo",
                "cp": "27001",
                "lat": 43.0,
                "lon": -7.5,
                "telefono": "982111111",
                "email": "a@test.gal",
            },
            {
                "id": "GAL-002",
                "nome": "ITV Lugo B",
                "enderezo": "Rúa B 2",
                "concello": "Lugo",
                "provincia": "Lugo",
                "cp": "27001",
                "lat": 43.01,
                "lon": -7.51,
                "telefono": "982111111",  # DUPLICATE PHONE
                "email": "b@test.gal",
            },
        ]
        
        result = transformer.transform(stations)
        
        # Only one station should be kept
        assert len(result) == 1
        # One rejection for duplicate phone
        assert any(
            r["reason"] == "duplicate_phone_in_message"
            for r in transformer.rejected_items
        )

    def test_duplicate_email_within_message(self) -> None:
        """Test detection of duplicate email addresses."""
        transformer = CatalunyaTransformer()
        
        stations = [
            {
                "id": "CAT-001",
                "nom": "ITV Tarragona A",
                "adreca": "Carrer A 1",
                "ciutat": "Tarragona",
                "provincia": "Tarragona",
                "codi_postal": "43001",
                "latitud": 41.1,
                "longitud": 1.2,
                "telefon": "977111111",
                "email": "shared@test.cat",
            },
            {
                "id": "CAT-002",
                "nom": "ITV Tarragona B",
                "adreca": "Carrer B 2",
                "ciutat": "Tarragona",
                "provincia": "Tarragona",
                "codi_postal": "43001",
                "latitud": 41.11,
                "longitud": 1.21,
                "telefon": "977222222",
                "email": "shared@test.cat",  # DUPLICATE EMAIL
            },
        ]
        
        result = transformer.transform(stations)
        
        # Only one station should be kept
        assert len(result) == 1
        # One rejection for duplicate email
        assert any(
            r["reason"] == "duplicate_email_in_message"
            for r in transformer.rejected_items
        )
