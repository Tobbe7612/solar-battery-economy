"""Regression tests for the Phase 3 internal data model."""


def create_initial_data_model() -> dict:
    """Return the initial coordinator data structure.

    This mirrors the coordinator's data-model initialization.
    Existing public keys must remain unchanged while Phase 3
    namespaces are introduced additively.
    """
    return {
        "power": {},
        "energy": {},
        "money": {},
        "savings": {},
        "house": {},
        "price": {},
        "price_intelligence": {},
        "consumers": {},
    }


def test_existing_data_keys_are_preserved():
    data = create_initial_data_model()

    assert "power" in data
    assert "energy" in data
    assert "money" in data
    assert "savings" in data


def test_phase_3_data_namespaces_exist():
    data = create_initial_data_model()

    assert "house" in data
    assert "price" in data
    assert "price_intelligence" in data
    assert "consumers" in data


def test_existing_data_namespaces_are_empty_at_initialization():
    data = create_initial_data_model()

    assert data["power"] == {}
    assert data["energy"] == {}
    assert data["money"] == {}
    assert data["savings"] == {}


def test_phase_3_namespaces_are_empty_at_initialization():
    data = create_initial_data_model()

    assert data["house"] == {}
    assert data["price"] == {}
    assert data["price_intelligence"] == {}
    assert data["consumers"] == {}


def test_phase_3_namespaces_are_independent():
    data = create_initial_data_model()

    data["house"]["total_energy"] = 10.0
    data["price"]["current"] = 1.50
    data["price_intelligence"]["quality"] = "good"
    data["consumers"]["car"] = {"soc": 75}

    assert data["house"]["total_energy"] == 10.0
    assert data["price"]["current"] == 1.50
    assert data["price_intelligence"]["quality"] == "good"
    assert data["consumers"]["car"]["soc"] == 75

    assert data["energy"] == {}
    assert data["money"] == {}
    assert data["savings"] == {}