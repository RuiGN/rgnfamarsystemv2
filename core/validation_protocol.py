from pathlib import Path


def evaluate_validation_protocol(path=None):
    path = Path(path or Path(__file__).resolve().parents[1] / 'docs/validation/iq-oq-pq-matrix.yml')
    data = __import__('yaml').safe_load(path.read_text(encoding='utf-8'))
    required = {'id', 'phase', 'objective', 'acceptance', 'owner'}
    results = [
        {
            'id': x.get('id', 'unknown'),
            'passed': required <= x.keys() and x.get('phase') in {'IQ', 'OQ', 'PQ'},
        }
        for x in data.get('protocols', [])
    ]
    return {'passed': bool(results) and all(x['passed'] for x in results), 'protocols': results}
