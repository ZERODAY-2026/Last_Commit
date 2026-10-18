from datamind.number_check import answer_numbers_are_grounded


def test_numbers_must_come_from_rows():
    assert answer_numbers_are_grounded("There are 10 orders.", [{"COUNT": 10}])
    assert not answer_numbers_are_grounded("There are 11 orders.", [{"COUNT": 10}])
