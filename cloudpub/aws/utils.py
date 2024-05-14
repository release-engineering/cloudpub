# SPDX-License-Identifier: GPL-3.0-or-later
import logging
from pprint import pformat
from typing import Any, Dict, List, Mapping, Tuple

import dateutil.parser
from packaging.version import InvalidVersion, Version

from cloudpub.models.aws import GroupedVersions


def create_version_tree(versions: Dict[str, GroupedVersions]) -> Dict[str, Any]:
    """
    Create a version sorted tree.

    Args:
        versions (Dict[str, GroupedVersions])
            The versions to create the tree from.
    Returns:
        Dict[str, Any]: Dict of the version tree
    """
    version_tree: Dict[str, Any] = {}
    for version, info in versions.items():
        try:
            # Try to pull version from first split
            # If we can't get the version then we just don't add it to dict
            version_number = Version(version.split(" ")[0])
        except InvalidVersion:
            continue
        major = str(version_number.major)
        minor = str(version_number.minor)
        if not version_tree.get(major):
            version_tree[major] = {}
        if not version_tree[major].get(minor):
            version_tree[major][minor] = {}
        if info["delivery_options"][0].visibility == "Public":
            version_tree[major][minor][version] = info
    return version_tree


def get_restricted_major_versions(
    version_tree: Dict[str, Any], restrict_major: int
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """
    Get all the restricted major versions.

    Args:
        version_tree (Dict[str, Any])
            The dict tree to pull major versions from.
        restrict_major (int)
            How many major versions to restrict to.
    Returns:
        Tuple[List[str], List[str], Dict[str, Any]]
            Tuple of restricted delivery ids, restricted ami ids,
            and updated version_tree
    """
    restrict_delivery_ids = []
    restrict_ami_ids = []
    version_list = sorted(version_tree.keys(), reverse=True, key=lambda x: int(x))
    for v in version_list[restrict_major:]:
        for s in version_tree[v].values():
            for x in s.values():
                delivery_options = x["delivery_options"]
                restrict_delivery_ids.append(delivery_options[0].id)
                restrict_ami_ids.extend(x["ami_ids"])
        del version_tree[v]
    return restrict_delivery_ids, restrict_ami_ids, version_tree


def get_restricted_minor_versions(
    version_tree: Dict[str, Any], restrict_minor: int
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """
    Get all the restricted major versions.

    Args:
        version_tree (Dict[str, Any])
            The dict tree to pull major versions from.
        restrict_minor (int)
            How many minor versions to restrict to.
    Returns:
        Tuple[List[str], List[str], Dict[str, Any]]
            Tuple of restricted delivery ids, restricted ami ids,
            and updated version_tree
    """
    restrict_delivery_ids = []
    restrict_ami_ids = []
    version_major_list = list(version_tree.keys())
    for major_version in version_major_list:
        version_list = sorted(
            version_tree[major_version].keys(), reverse=True, key=lambda x: int(x)
        )
        for v in version_list[restrict_minor:]:
            for s in version_tree[major_version][v].values():
                delivery_options = s["delivery_options"]
                restrict_delivery_ids.append(delivery_options[0].id)
                restrict_ami_ids.extend(s["ami_ids"])
            del version_tree[major_version][v]
    return restrict_delivery_ids, restrict_ami_ids, version_tree


def get_restricted_patch_versions(version_tree: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Get all the patch versions to latest.

    Args:
        version_tree (Dict[str, Any])
            The dict tree to pull major versions from.
    Returns:
        Tuple[List[str], List[str]]: Tuple of restricted delivery ids and restricted ami ids
    """
    restrict_delivery_ids = []
    restrict_ami_ids = []
    for major in version_tree.values():
        for minor in major.values():
            ordered_versions = sorted(
                minor.values(),
                key=lambda x: dateutil.parser.isoparse(x["created_date"]),
                reverse=True,
            )
            for x in ordered_versions[1:]:
                delivery_options = x["delivery_options"]
                restrict_delivery_ids.append(delivery_options[0].id)
                restrict_ami_ids.extend(x["ami_ids"])
    return restrict_delivery_ids, restrict_ami_ids


def pprint_debug_logging(
    log: logging.Logger, rsp_log: Mapping[str, Any], log_tag: str = "Response: "
) -> None:
    """
    Pprint a dict into the appropriate logger.

    Args:
        log (Logger)
            The log to report to.
        rsp_log (Dict[str, Any])
            The dict to add to logging.
    Returns:
        None
    """
    if log.isEnabledFor(logging.DEBUG):
        log.debug("%s\n%s", log_tag, pformat(rsp_log))
