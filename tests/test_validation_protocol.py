from core.validation_protocol import evaluate_validation_protocol


def test_validation_protocol_covers_iq_oq_pq():
    report = evaluate_validation_protocol()
    assert report['passed'] is True
    assert {x['id'] for x in report['protocols']} == {'IQ-001', 'OQ-001', 'PQ-001'}
