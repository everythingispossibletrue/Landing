"""Small HTML reader used to derive structured data from visible page content.

This is a reader, not a serializer: it never rewrites the page markup.
"""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re

VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
TEXT_BREAK_ELEMENTS = {
    "address", "article", "aside", "blockquote", "br", "div", "dl", "dt", "dd",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
    "header", "hr", "li", "main", "nav", "ol", "p", "pre", "section", "table",
    "td", "th", "tr", "ul",
}
PARAGRAPH_END_ELEMENTS = {
    "address", "article", "aside", "blockquote", "div", "dl", "fieldset", "footer",
    "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hgroup", "hr",
    "main", "menu", "nav", "ol", "p", "pre", "section", "table", "ul",
}


@dataclass
class Element:
    tag: str
    attributes: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._text_parts())).strip()

    def _text_parts(self):
        for child in self.children:
            if not isinstance(child, Element):
                yield child
                continue
            if child.tag in {"script", "style"}:
                continue
            if child.tag in TEXT_BREAK_ELEMENTS:
                yield " "
            yield from child._text_parts()
            if child.tag in TEXT_BREAK_ELEMENTS:
                yield " "

    def find_all(self, tag=None, class_name=None, *, element_id=None, recursive=True):
        """Yield matching descendants in document order."""
        for child in self.children:
            if not isinstance(child, Element):
                continue

            matches_tag = tag is None or child.tag == tag
            classes = (child.attributes.get("class") or "").split()
            matches_class = class_name is None or class_name in classes
            matches_id = element_id is None or child.attributes.get("id") == element_id
            if matches_tag and matches_class and matches_id:
                yield child
            if recursive:
                yield from child.find_all(tag, class_name, element_id=element_id)

    def require(self, tag=None, class_name=None, *, element_id=None):
        match = next(self.find_all(tag, class_name, element_id=element_id), None)
        if match is None:
            raise ValueError(
                f"Missing required HTML element: tag={tag!r}, "
                f"class={class_name!r}, id={element_id!r}"
            )
        return match


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.document = Element("document")
        self.stack = [self.document]

    def handle_starttag(self, tag, attributes):
        # HTML permits omitted closing tags for list items and paragraphs.
        if tag == "li":
            self._close_optional_element({"li"}, {"ul", "ol"})
        elif tag in {"dt", "dd"}:
            self._close_optional_element({"dt", "dd"}, {"dl"})
        if tag in PARAGRAPH_END_ELEMENTS:
            self._close_optional_element({"p"}, {"document"})
        element = Element(tag, dict(attributes))
        self.stack[-1].children.append(element)
        if tag not in VOID_ELEMENTS:
            self.stack.append(element)

    def _close_optional_element(self, tags, boundaries):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag in tags:
                del self.stack[index:]
                return
            if self.stack[index].tag in boundaries:
                return

    def handle_startendtag(self, tag, attributes):
        self.stack[-1].children.append(Element(tag, dict(attributes)))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(markup: str) -> Element:
    parser = DocumentParser()
    parser.feed(markup)
    parser.close()
    return parser.document
