# An extension to add an index of attributes within class docs.
#
# This extension was based on pushsource's external sphinx extension:
# https://github.com/release-engineering/pushsource/blob/master/docs/ext/attr_index.py
#
# For classes using attrs, this will produce a list under the class description
# of the form:
#
#  Attributes:
#    - base-attr [inherited]
#    - other-base-attr [inherited]
#    - my-own-attr
#    - my-other-attr
#    - (...etc)
#
# The motivation is to make it easier to navigate around our quite large set
# of attributes and also to improve visibility of inherited attributes on
# subclasses (without duplicating their entire doc strings).
#
from typing import Any, List, Optional, Type

from sphinx.application import Sphinx


def find_owning_class(klass: Type[object], attr_name: str) -> Optional[Type[object]]:
    # Given an attribute name and a class on which it was found, return
    # the class which owns that attribute (as opposed to inheriting it)
    for candidate in klass.__mro__:
        if not hasattr(candidate, "__attrs_attrs__"):
            continue

        attr = getattr(candidate.__attrs_attrs__, attr_name)
        if not attr.inherited:
            # It belongs here
            return candidate
    return None


def add_attr_index(
    app: Sphinx, what: str, name: str, obj: Any, options: Any, lines: List[str]
) -> None:
    if not hasattr(obj, "__attrs_attrs__"):
        return

    attrs = sorted(obj.__attrs_attrs__, key=lambda attr: (not attr.inherited, attr.name))
    if not attrs:
        return

    # We've got some attributes. Let's produce an index of them, linking to both
    # the inherited and local attributes.

    lines.extend(["", "**Attributes:**", ""])
    for attr in attrs:
        if attr.inherited:
            klass = find_owning_class(obj, attr.name)
            if klass:
                line = f"* :meth:`~cloudpub.{klass.__name__}.{attr.name}` *[inherited]*"
        else:
            line = f"* :meth:`{attr.name}`"

        lines.append(line)
    lines.extend(["", ""])


def setup(app: Sphinx):
    # entrypoint invoked by sphinx when extension is loaded
    app.connect("autodoc-process-docstring", add_attr_index)
