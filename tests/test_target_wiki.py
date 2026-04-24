import pytest
from openscad_docsgen.target_wiki import Target_Wiki


@pytest.fixture
def target():
    return Target_Wiki(project_name="TestProject", docs_dir="docs")


# --- Metadata ---

def test_get_suffix(target):
    assert target.get_suffix() == ".md"


# --- escape_entities ---

def test_escape_underscore(target):
    assert target.escape_entities("foo_bar") == r"foo\_bar"


def test_escape_ampersand(target):
    assert target.escape_entities("A&B") == "A&amp;B"


def test_escape_less_than(target):
    assert target.escape_entities("A<B") == "A&lt;B"


def test_escape_greater_than(target):
    assert target.escape_entities("A>B") == "A&gt;B"


def test_escape_plain_text(target):
    assert target.escape_entities("hello world") == "hello world"


def test_escape_skips_backtick_content(target):
    result = target.escape_entities("foo_bar `baz_qux`")
    assert r"foo\_bar" in result
    assert "`baz_qux`" in result
    assert r"baz\_qux" not in result


def test_escape_multiple_underscores(target):
    result = target.escape_entities("a_b_c")
    assert result == r"a\_b\_c"


# --- bold / italics / code_span ---

def test_bold(target):
    assert target.bold("text") == "**text**"


def test_italics(target):
    assert target.italics("text") == "*text*"


def test_code_span(target):
    assert target.code_span("foo()") == "<code>foo()</code>"


# --- header_link ---

def test_header_link_lowercase(target):
    assert target.header_link("MySection") == "mysection"


def test_header_link_spaces_to_dashes(target):
    assert target.header_link("foo bar") == "foo-bar"


def test_header_link_removes_special_chars(target):
    assert target.header_link("Foo & Bar") == "foo--bar"


def test_header_link_function_colon(target):
    result = target.header_link("Function: foo_bar")
    assert result == "function-foo_bar"


def test_header_link_keeps_underscore(target):
    assert target.header_link("foo_bar") == "foo_bar"


# --- header ---

def test_header_lev1(target):
    lines = target.header("Title", lev=1)
    assert lines == ["# Title", ""]


def test_header_lev2(target):
    lines = target.header("Section", lev=2)
    assert lines[0] == "## Section"


def test_header_lev3(target):
    lines = target.header("Item", lev=3)
    assert lines[0] == "### Item"


def test_header_escapes_by_default(target):
    lines = target.header("foo_bar", lev=1)
    assert r"foo\_bar" in lines[0]


def test_header_no_escape(target):
    lines = target.header("**bold**", lev=1, esc=False)
    assert "**bold**" in lines[0]


def test_header_ends_with_blank(target):
    lines = target.header("X", lev=1)
    assert lines[-1] == ""


# --- block_header ---

def test_block_header_title_and_subtitle(target):
    lines = target.block_header("Title", "subtitle text")
    assert lines[0] == "**Title:** subtitle text"
    assert lines[1] == ""


def test_block_header_no_subtitle(target):
    lines = target.block_header("Title")
    assert lines[0] == "**Title:** "


# --- get_link ---

def test_get_link_with_anchor_and_file(target):
    link = target.get_link("foo", anchor="foo", file="MyFile")
    assert link == "[`foo`](MyFile#foo)"


def test_get_link_no_anchor(target):
    link = target.get_link("foo", file="MyFile")
    assert link == "[`foo`](MyFile)"


def test_get_link_no_literalize(target):
    link = target.get_link("foo", anchor="foo", file="MyFile", literalize=False)
    assert link == "[foo](MyFile#foo)"


def test_get_link_html(target):
    link = target.get_link("foo", anchor="bar", file="MyFile", html=True)
    assert link == '<a href="MyFile#bar">`foo`</a>'


def test_get_link_empty_anchor(target):
    link = target.get_link("foo", anchor="", file="MyFile")
    assert link == "[`foo`](MyFile)"


# --- indent_lines ---

def test_indent_lines(target):
    assert target.indent_lines(["a", "b"]) == ["    a", "    b"]


def test_indent_lines_empty(target):
    assert target.indent_lines([]) == []


# --- horizontal_rule ---

def test_horizontal_rule(target):
    assert target.horizontal_rule() == ["---", ""]


# --- bullet list ---

def test_bullet_list_item(target):
    assert target.bullet_list_item("foo") == ["- foo"]


def test_bullet_list(target):
    result = target.bullet_list(["a", "b", "c"])
    assert "- a" in result
    assert "- b" in result
    assert "- c" in result


def test_bullet_list_empty(target):
    result = target.bullet_list([])
    assert result == [""]


# --- numbered list ---

def test_numbered_list_item(target):
    assert target.numbered_list_item(1, "first") == ["1. first"]


def test_numbered_list(target):
    result = target.numbered_list(["a", "b"])
    assert "1. a" in result
    assert "2. b" in result


# --- table ---

def test_table_basic(target):
    headers = ["Name", "Value"]
    rows = [["foo", "bar"], ["baz", "qux"]]
    result = target.table(headers, rows)
    assert result[0] == "Name | Value"
    assert "foo | bar" in result
    assert "baz | qux" in result


def test_table_separator_row(target):
    headers = ["Name", "Value"]
    rows = []
    result = target.table(headers, rows)
    assert result[0] == "Name | Value"
    assert result[1] == "---- | -----"


def test_table_caret_strips_from_header(target):
    headers = ["^Name", "Value"]
    rows = [["foo", "bar"]]
    result = target.table(headers, rows)
    assert "Name" in result[0]
    assert "^Name" not in result[0]


def test_table_caret_formats_cell(target):
    headers = ["^Arg", "Description"]
    rows = [["arg1/arg2", "desc"]]
    result = target.table(headers, rows)
    cell_line = [l for l in result if "arg1" in l][0]
    assert "`arg1`" in cell_line


# --- code_block ---

def test_code_block_nonempty(target):
    result = target.code_block(["sphere(10);"])
    assert "``` {.C linenos=True}" in result
    assert "sphere(10);" in result
    assert "```" in result


def test_code_block_empty(target):
    assert target.code_block([]) == []


# --- quote / line_with_break / paragraph ---

def test_quote_list(target):
    assert target.quote(["line1", "line2"]) == [">line1", ">line2"]


def test_quote_string(target):
    assert target.quote("single") == [">single"]


def test_line_with_break_string(target):
    assert target.line_with_break("hello") == ["hello  "]


def test_line_with_break_list(target):
    assert target.line_with_break(["a", "b"]) == ["a", "b  "]


def test_paragraph(target):
    result = target.paragraph(["line"])
    assert result[-1] == ""
