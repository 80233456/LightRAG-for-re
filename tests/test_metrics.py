from evidencechain.metrics import answer_em, answer_f1, binary_metrics, fact_recall


def test_answer_metrics():
    assert answer_em("Paris", "paris") == 1
    assert answer_f1("Paris city", "Paris") > 0
    assert answer_em("London", "Paris") == 0


def test_binary_metrics():
    x = binary_metrics([True, False, True, False], [True, False, False, True])
    assert x["accuracy"] == 0.5 and x["tp"] == 1


def test_fact_recall():
    assert fact_recall(["A is in London", "B is in Paris"], ["in London", "in Mars"]) == .5
