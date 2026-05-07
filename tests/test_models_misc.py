from cp2graph.models import CPModelIR, Domain, Variable


def test_domain_size_variants() -> None:
    assert Domain(kind="bool").size == 2
    assert Domain(kind="int-set", values=[1, 1, 2]).size == 2
    assert Domain(kind="int-bounds", lower=1, upper=3).size == 3
    assert Domain(kind="float-bounds", lower=0.0, upper=1.0).size is None
    assert Domain(kind="unknown").size is None


def test_model_copy() -> None:
    m = CPModelIR()
    m.variables["x"] = Variable(id="x", name="x", domain=Domain(kind="bool"))
    c = m.copy()
    assert "x" in c.variables
