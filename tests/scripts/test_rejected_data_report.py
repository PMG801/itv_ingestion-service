from __future__ import annotations

from datetime import datetime, timezone

from scripts.rejected_data_report import (
    RejectedDataReport,
    _build_amqp_url,
    classify_reason,
    render_text_report,
)


def test_classify_reason_groups_common_failures() -> None:
    assert classify_reason("missing_raw_id") == "missing_data"
    assert classify_reason("invalid_email_format") == "validation"
    assert classify_reason("duplicate_phone_in_message") == "duplicate_detection"
    assert classify_reason("station_transform_exception") == "processing"
    assert classify_reason("no_stations_extracted") == "message_empty"


def test_rejected_data_report_collects_statistics() -> None:
    report = RejectedDataReport(queue_name="rejected_data.itv_stations")

    report.add_message(
        {
            "message_id": "msg-1",
            "source": "catalunya",
            "format": "xml",
            "reason": "missing_raw_id",
            "rejection_level": "station",
            "raw_payload": {"nom": "ITV Nord"},
            "rejected_at": "2026-04-01T10:00:00Z",
        }
    )
    report.add_message(
        {
            "message_id": "msg-2",
            "source": "valencia",
            "format": "json",
            "reason": "invalid_email_format",
            "rejection_level": "station",
            "raw_payload": '{"correo": "bad"}',
            "rejected_at": datetime(2026, 4, 1, 10, 5, tzinfo=timezone.utc),
        }
    )

    assert report.total_messages == 2
    assert report.reason_counts["missing_raw_id"] == 1
    assert report.reason_counts["invalid_email_format"] == 1
    assert report.reason_family_counts["missing_data"] == 1
    assert report.reason_family_counts["validation"] == 1
    assert report.source_counts["catalunya"] == 1
    assert report.source_counts["valencia"] == 1
    assert report.raw_payload_type_counts["dict"] == 1
    assert report.raw_payload_type_counts["str"] == 1
    assert report.first_rejected_at is not None
    assert report.last_rejected_at is not None
    assert report.first_rejected_at.isoformat() == "2026-04-01T10:00:00+00:00"
    assert report.last_rejected_at.isoformat() == "2026-04-01T10:05:00+00:00"
    assert report.sample_by_reason["missing_raw_id"]["message_id"] == "msg-1"


def test_render_text_report_includes_key_sections() -> None:
    report = RejectedDataReport(queue_name="rejected_data.itv_stations")
    report.add_message(
        {
            "message_id": "msg-1",
            "source": "galicia",
            "format": "csv",
            "reason": "schema_validation_failed",
            "rejection_level": "station",
            "raw_payload": {"id": "GAL-1"},
        }
    )

    text = render_text_report(report)

    assert "Informe de rejected_data.itv_stations" in text
    assert "Familias de fallo" in text
    assert "schema_validation_failed" in text


def test_build_amqp_url_prefers_explicit_url() -> None:
    assert (
        _build_amqp_url(
            rabbitmq_url="amqp://user:pass@host:5672/vhost",
            host="ignored",
            port=5672,
            user="ignored",
            password="ignored",
            vhost="ignored",
        )
        == "amqp://user:pass@host:5672/vhost"
    )


def test_build_amqp_url_uses_components_when_url_missing() -> None:
    assert (
        _build_amqp_url(
            rabbitmq_url=None,
            host="localhost",
            port=5673,
            user="admin",
            password="secret",
            vhost="/itv_data",
        )
        == "amqp://admin:secret@localhost:5673/itv_data"
    )
