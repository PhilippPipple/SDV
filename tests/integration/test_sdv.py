from sdv import SDV, load_demo


def test_sdv():
    metadata, tables = load_demo(metadata=True)

    sdv = SDV()
    sdv.fit(metadata, tables)

    # Sample all
    sampled = sdv.sample_all()

    assert set(sampled.keys()) == {'users', 'sessions', 'transactions'}
    assert len(sampled['users']) == 10

    # Sample with children
    sampled = sdv.sample('users', reset_primary_keys=True)

    assert set(sampled.keys()) == {'users', 'sessions', 'transactions'}
    assert len(sampled['users']) == 10

    # Sample without children
    users = sdv.sample('users', sample_children=False)

    assert users.shape == tables['users'].shape
    assert list(users.columns) == list(tables['users'].columns)

    sessions = sdv.sample('sessions', sample_children=False)

    assert sessions.shape == tables['sessions'].shape
    assert list(sessions.columns) == list(tables['sessions'].columns)

    transactions = sdv.sample('transactions', sample_children=False)

    assert transactions.shape == tables['transactions'].shape
    assert list(transactions.columns) == list(tables['transactions'].columns)
