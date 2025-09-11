import types

from manic.processors.calibration import calculate_background_ratios, calculate_mrrf_values


class StubProvider:
    def __init__(self, samples_map):
        self._samples_map = samples_map

    def resolve_mm_samples(self, mm_field):
        # Ignore mm_field pattern and return fixed samples for test
        return list(self._samples_map.keys())

    def get_sample_corrected_data(self, sample_name):
        return self._samples_map.get(sample_name, {})


def test_calculate_background_ratios_simple():
    # Compound A: in two standard samples
    samples_map = {
        'std1': {'A': [100.0, 20.0, 10.0]},  # unlabeled=100, labeled=30
        'std2': {'A': [50.0, 5.0, 5.0]},     # unlabeled=50, labeled=10
    }
    provider = StubProvider(samples_map)
    compounds = [{
        'compound_name': 'A',
        'label_atoms': 2,
        'mm_files': 'std*',
    }]

    ratios = calculate_background_ratios(provider, compounds)
    # Means: unlabeled=(100+50)/2 = 75; labeled=(30+10)/2 = 20 => ratio=20/75
    assert 'A' in ratios
    assert abs(ratios['A'] - (20.0 / 75.0)) < 1e-9


def test_calculate_mrrf_values_means(monkeypatch):
    # Provide two standard samples, totals for metabolite A and internal standard ISTD
    samples_map = {
        'std1': {
            'A': [100.0, 0.0],    # total 100
            'ISTD': [20.0],       # total 20
        },
        'std2': {
            'A': [200.0, 0.0],    # total 200
            'ISTD': [40.0],       # total 40
        },
    }
    provider = StubProvider(samples_map)
    compounds = [{
        'compound_name': 'A',
        'amount_in_std_mix': 2.0,  # metabolite concentration in standard mix
        'mm_files': 'std*',
    }, {
        'compound_name': 'ISTD',
        'amount_in_std_mix': 1.0,
        'mm_files': 'std*',
    }]

    # Fake DB connection to supply internal standard concentration and mm_files
    class Row(dict):
        def __getattr__(self, k):
            return self[k]

    class FakeCursor:
        def __init__(self, rows):
            self._rows = rows
        def fetchone(self):
            return self._rows[0] if self._rows else None
        def fetchall(self):
            return self._rows

    class FakeConn:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def execute(self, sql, params=()):
            sql_u = sql.lower()
            if 'select amount_in_std_mix' in sql_u:
                # Return 1.0 for internal standard concentration
                return FakeCursor([Row({'amount_in_std_mix': 1.0})])
            if 'select mm_files' in sql_u:
                return FakeCursor([Row({'mm_files': 'std*'})])
            return FakeCursor([])

    import manic.models.database as dbmod
    monkeypatch.setattr(dbmod, 'get_connection', lambda: FakeConn())

    mrrf = calculate_mrrf_values(provider, compounds, 'ISTD')
    # Means: metabolite= (100+200)/2=150; internal std= (20+40)/2=30
    # MRRF = (150/2.0) / (30/1.0) = 75/30 = 2.5
    assert abs(mrrf['A'] - 2.5) < 1e-9
    assert abs(mrrf['ISTD'] - 1.0) < 1e-9

