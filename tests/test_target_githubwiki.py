from openscad_docsgen.target_githubwiki import Target_GitHubWiki


def test_get_suffix():
    t = Target_GitHubWiki()
    assert t.get_suffix() == ".md"


def test_code_block_indented():
    t = Target_GitHubWiki()
    result = t.code_block(["sphere(10);", "cube(5);"])
    assert "    sphere(10);" in result
    assert "    cube(5);" in result


def test_code_block_empty():
    t = Target_GitHubWiki()
    assert t.code_block([]) == []


def test_image_basic():
    t = Target_GitHubWiki()
    result = t.image("myFunc", "Example 1", "images/mylib/myFunc.png")
    assert len(result) == 2
    assert result[1] == ""
    assert '<img align="left"' in result[0]
    assert 'src="images/mylib/myFunc.png"' in result[0]
    assert "myFunc" in result[0]


def test_image_no_size_no_width_height_attrs():
    t = Target_GitHubWiki()
    result = t.image("foo", "Ex 1", "img/foo.png")
    assert 'width=' not in result[0]
    assert 'height=' not in result[0]


def test_image_with_width():
    t = Target_GitHubWiki()
    result = t.image("foo", "Ex 1", "img/foo.png", width=320, height=240)
    assert 'width="320"' in result[0]


def test_image_escapes_entities():
    t = Target_GitHubWiki()
    result = t.image("foo_bar", "Ex 1", "img/foo.png")
    assert r"foo\_bar" in result[0]


def test_image_block_renders_code():
    t = Target_GitHubWiki()
    result = t.image_block("myFunc", "Example 1", code=["sphere(10);"])
    code_line = [l for l in result if "sphere" in l]
    assert len(code_line) > 0


def test_image_block_with_url():
    t = Target_GitHubWiki()
    result = t.image_block("myFunc", "Example 1", rel_url="images/myFunc/myFunc.png")
    assert any('<img' in l for l in result)
