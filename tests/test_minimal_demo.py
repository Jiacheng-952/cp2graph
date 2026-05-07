from cp2graph import parse_model_text_to_graph


def test_minimal_demo_graph_build() -> None:
    text = """
var 0..10: x;
var 0..10: y;
constraint int_lin_eq([1,2],[x,y],7);
solve satisfy;
""".strip()
    g = parse_model_text_to_graph(text, normalize=True)
    assert g.number_of_nodes() >= 3
    assert g.number_of_edges() >= 4
