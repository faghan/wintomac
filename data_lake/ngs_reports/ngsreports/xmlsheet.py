import html.parser


class IlluminaXMLError(Exception):
    pass


class IlluminaXMLParser(html.parser.HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.root = {"tag": None, "attrs": None, "children": [], "data": None}
        self._stack = [self.root]

        self.feed(text)

    def handle_starttag(self, tag, attrs):
        tag = {"tag": tag, "attrs": attrs, "children": [], "data": None}

        if self._stack:
            self._stack[-1]["children"].append(tag)
        self._stack.append(tag)
        if self.root is None:
            self.root = tag

    def handle_endtag(self, tag):
        if not self._stack:
            raise IlluminaXMLError(f"orphan end-tag found: {tag}")
        elif self._stack[-1]["tag"] != tag:
            raise IlluminaXMLError(
                f"mismatching end-tag; expected {self._stack[-1]['tag']}, found {tag}"
            )

        self._stack.pop()

    def handle_data(self, data):
        data = data.strip()
        if not data:
            return  # Don't trigger on trailing newlines
        elif not self._stack:
            raise IlluminaXMLError(f"orphan data found: {data!r}")

        self._stack[-1]["data"] = data


class IlluminaXML:
    def __init__(self, node):
        self._node = node

    @classmethod
    def from_file(self, filepath):
        with open(filepath, "rt") as handle:
            parser = IlluminaXMLParser(handle.read())

            return IlluminaXML(parser.root)

    def first_child(self, tag):
        for child in self._node["children"]:
            if child["tag"].lower() == tag.lower():
                return IlluminaXML(child)

        raise KeyError(tag)

    @property
    def children(self):
        return [IlluminaXML(child) for child in self._node["children"]]

    @property
    def data(self):
        return self._node["data"]
