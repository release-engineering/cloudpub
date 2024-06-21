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
            return

        # Ensure it's a dictionary
        cls._assert_json_dict(json)

        # Copy the JSON so we can modify the data without destroying the original dict.
        json_copy = deepcopy(json)

        # Resolve the aliases in JSON to avoid breaking the class construction
        attributes: Tuple[Attribute] = cls.__attrs_attrs__  # type: ignore
        for at in attributes:
            alias = at.metadata.get("alias")
            if alias:
                alias_value = json_copy.pop(alias, None)
                if alias_value is not None:
                    json_copy[at.name] = alias_value
            # Add defaults to unset attributes when required
            default = at.metadata.get("default")
            if default and not json_copy.get(at.name):
                json_copy[at.name] = default
            # If a constant is set we need to override the value coming from JSON
            constant = at.metadata.get("const")
            if constant:
                json_copy[at.name] = constant

        # Run the preprocessing if any
        json_copy = cls._preprocess_json(json_copy)

        args = {}
        cls_attr = [a.name for a in cls.__attrs_attrs__ if isinstance(a, Attribute)]  # type: ignore
        for a in cls_attr:
            args[a] = json_copy.pop(a, None)

        # Log any unused attributes
        for k in json_copy.keys():
            log.warning(f"Ignoring unknown attribute {k} from {cls.__name__}.")

        return cls(**args)

    @staticmethod
    def _serialize_value(attribute: Attribute, value: Any) -> Any:
        """Iteractively parse and serialize the received value to a Python builtin.

        Args:
            attribute (Attribute): The attrs attribute to receive the value
            value (Any): The value to be parsed/serialized

        Returns:
            Any: The parsed/serialized value
        """
        if isinstance(value, list):
            value = [x.to_json() if hasattr(x, "to_json") else x for x in value]
        elif isinstance(value, dict):
            value = {k: v.to_json() if hasattr(v, "to_json") else v for k, v in value.items()}
        elif isinstance(value, object) and hasattr(value, "to_json"):
            value = value.to_json()
        return value

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
        for at in attributes:
            value = getattr(self_copy, at.name, None)
            if value is not None:
                value = self._serialize_value(at, value)
                setattr(self_copy, at.name, value)

        # Convert the instance to dictionary
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
                json[alias] = json.pop(at.name)

        return json
