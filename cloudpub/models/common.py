# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from copy import deepcopy
from typing import Any, Dict, Tuple

from attrs import Attribute, asdict, define

log = logging.getLogger(__name__)


@define
class AttrsJSONDecodeMixin:
    """Implement the default JSON (de)serialization for attrs decorated classes."""

    @classmethod
    def _assert_json_dict(cls, json: Any) -> None:
        """
        Ensure the given JSON is an instance of `dict`.

        Args:
            json (Any)
                A JSON response to ensure its a dictionary.
        """
        if not isinstance(json, dict):
            msg = f"Got an unsupported JSON type: \"{type(json)}\". Expected: \"<class 'dict'>\'"
            log.error(msg)
            raise ValueError(msg)

    @classmethod
    def _preprocess_json(cls, json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess the JSON before converting it to class object.

        It's intended to be overriden by base classes which needs to do it.

        Args:
            json (dict)
                A JSON containing the data to be converted.
        Returns:
            dict: The modified JSON.
        """
        return json

    @classmethod
    def from_json(cls, json: Any):
        """
        Convert a JSON dictionary into class object.

        Args:
            json (dict)
                A JSON containing a the attrs class keys.
        Returns:
            The converted object from JSON.
        """
        if not json:
            log.debug("Not converting an empty JSON.")
            return

        # Ensure it's a dictionary
        log.debug("Converting the following json into class %s: %s" % (cls.__name__, json))
        cls._assert_json_dict(json)

        # Copy the JSON so we can modify the data without destroying the original dict.
        json_copy = deepcopy(json)

        # Resolve the aliases in JSON to avoid breaking the class construction
        attributes: Tuple[Attribute] = cls.__attrs_attrs__  # type: ignore
        for at in attributes:
            alias = at.metadata.get("alias")
            if alias and json.get(alias, None) is not None:
                log.debug("Resolving the alias: \"%s\" into \"%s\"." % (alias, at.name))
                json_copy[at.name] = json_copy.pop(alias)

        # Run the preprocessing if any
        json_copy = cls._preprocess_json(json_copy)

        args = {}
        cls_attr = [a.name for a in cls.__attrs_attrs__ if isinstance(a, Attribute)]  # type: ignore
        for a in cls_attr:
            log.debug("Assigning the attribute %s to %s" % (a, cls.__name__))
            args[a] = json_copy.pop(a, None)
        return cls(**args)

    def to_json(self):
        """
        Convert a class object mapped by attrs into a dictionary.

        Returns:
            dict: The JSON from object.
        """
        # To avoid recursively messing with the internal parameters we will make a copy of self
        self_copy = deepcopy(self)

        # Convert the instance sub-elements into dictionary
        attributes: Tuple[Attribute] = self_copy.__attrs_attrs__  # type: ignore
        klass_name = self_copy.__class__.__name__
        for at in attributes:
            value = getattr(self_copy, at.name, None)
            if value is not None:
                log.debug("Parsing the attribute \"%s\" from \"%s\"" % (at.name, klass_name))
                if isinstance(value, list):
                    log.debug("Parsing the list from %s" % at.name)
                    value = [x.to_json() if hasattr(x, "to_json") else x for x in value]
                elif isinstance(value, dict):
                    log.debug("Parsing the dict from %s" % at.name)
                    value = {
                        k: v.to_json() if hasattr(v, "to_json") else v for k, v in value.items()
                    }
                elif isinstance(value, object) and hasattr(value, "to_json"):
                    log.debug("Recursively building the value from %s" % at.name)
                    value = value.to_json()
                elif value.__class__.__module__ == 'builtins':
                    log.debug(
                        "Not converting the object \"%s\" with value \"%s\" to JSON.",
                        type(value),
                        value,
                    )
                else:
                    log.warning(
                        "Not converting the object \"%s\" with value \"%s\" to JSON.",
                        type(value),
                        value,
                    )
                setattr(self_copy, at.name, value)

        # Convert the instance to dictionary
        log.debug("Converting the \"%s\" instance to dictionary" % klass_name)
        json = asdict(
            self_copy,
            recurse=False,
            filter=lambda k, v: not (k.metadata.get("hide_unset", False) and v is None),
        )

        # Resolve back the aliases
        attributes: Tuple[Attribute] = self_copy.__attrs_attrs__  # type: ignore
        for at in attributes:
            alias = at.metadata.get("alias")
            if alias and json.get(at.name, None) is not None:
                log.debug("Resolving back the alias: from \"%s\" in \"%s\"" % (alias, at.name))
                json[alias] = json.pop(at.name)

        log.debug("Resulting JSON from \"%s\" instance iteration: %s" % (klass_name, json))
        return json
