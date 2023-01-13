# This extension was based on pushsource's external sphinx extension:
# https://github.com/release-engineering/pushsource/blob/master/docs/ext/attr_types.py
import sys
from typing import Any, List, Optional, Type

import attr
from sphinx.application import Sphinx


def add_attr_types(
    app: Sphinx, what: str, name: str, obj: Type[object], options: Any, lines: List[str]
) -> None:
    # If we are generating docs for a field defined attribute
    # where 'type' has been set, append this type info to the
    # doc string in the format understood by sphinx.

    if what != "attribute":
        # not an attribute => nothing to do
        return

    if ":type:" in "".join(lines):
        # type has already been documented explicitly, don't
        # try to override it
        return

    components = name.split(".")
    if len(components) != 3 or components[0] != "cloudpub":
        # We are looking specifically for public fields of the form:
        # cloudpub.<class_name>.<attr_name>
        # For any other cases we'll do nothing.
        return

    (klass_name, field_name) = components[1:]
    klass = getattr(sys.modules["cloudpub"], klass_name)

    if not attr.has(klass):
        # not an attrs-using class, nothing to do
        return

    field = attr.fields_dict(klass).get(field_name)
    if not field:
        # not a field
        return

    type = field.type
    if not type:
        # no type hint declared, can't do anything
        return

    # phew, after all the above we know we're documenting an attrs-based
    # field and we know exactly what type it is, so add it to the end of
    # the doc string.
    lines.extend(["", f":type: {type.__name__}"])


def setup(app: Sphinx):
    # entrypoint invoked by sphinx when extension is loaded
    app.connect("autodoc-process-docstring", add_attr_types)
