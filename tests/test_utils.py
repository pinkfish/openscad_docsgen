from openscad_docsgen.utils import flatten


def test_flatten_empty():
    assert flatten([]) == []


def test_flatten_already_flat():
    assert flatten([1, 2, 3]) == [1, 2, 3]


def test_flatten_one_level():
    assert flatten([1, [2, 3], 4]) == [1, 2, 3, 4]


def test_flatten_deeply_nested():
    assert flatten([1, [2, [3, [4]]]]) == [1, 2, 3, 4]


def test_flatten_with_tuples():
    assert flatten([(1, 2), 3]) == [1, 2, 3]


def test_flatten_empty_inner_list():
    assert flatten([1, [], 2]) == [1, 2]


def test_flatten_returns_same_type_for_tuple():
    result = flatten((1, (2, 3)))
    assert isinstance(result, tuple)
    assert result == (1, 2, 3)


def test_flatten_multiple_empty_inner():
    assert flatten([[], [], []]) == []


def test_flatten_mixed_nesting():
    assert flatten([[1, 2], [3, [4, 5]]]) == [1, 2, 3, 4, 5]
