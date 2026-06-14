import builtins
import importlib
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import ponkan
from ponkan.profiles import (
    UnknownCaptureProfile,
    get_capture_profile,
    list_capture_profiles,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ROADMAP_TARGETS = (
    "old3ds",
    "o3ds",
    "classic_ds",
    "optimize",
    "nisetro",
    "is_nitro",
    "is_twl",
    "partner_ctr",
)


def test_list_capture_profiles_returns_immutable_tuple() -> None:
    profiles = list_capture_profiles()

    assert isinstance(profiles, tuple)
    with pytest.raises(FrozenInstanceError):
        profiles[0].__setattr__("id", "changed")


def test_n3dsxl_profile_metadata_matches_public_contract() -> None:
    profile = get_capture_profile("n3dsxl")

    assert profile.id == "n3dsxl"
    assert profile.display_name == "new 3DS XL"
    assert profile.model == "new_3ds_xl"
    assert profile.family == "3ds"
    assert profile.provider == "ponkan-python"
    assert profile.support_status == "stable"
    assert profile.default_output == "both_vertical"
    assert profile.default_colorspace == "RGB"
    assert profile.supported_colorspaces == ("RGB", "BGR")
    assert profile.native_fps == 59.8
    assert profile.screen_layout == "3ds_dual_screen"
    assert profile.supported_outputs == ("top", "bottom", "both_vertical")
    assert not profile.supports_3d
    assert not profile.supports_audio
    assert not profile.supports_recording


def test_new_3ds_xl_alias_resolves_to_n3dsxl_profile() -> None:
    assert get_capture_profile("new_3ds_xl") is get_capture_profile("n3dsxl")


def test_unknown_profile_raises_explicit_error() -> None:
    with pytest.raises(UnknownCaptureProfile, match="classic_ds"):
        get_capture_profile("classic_ds")


def test_future_profiles_are_not_returned_before_source_audit() -> None:
    profile_ids = {profile.id for profile in list_capture_profiles()}

    assert profile_ids == {"n3dsxl"}
    assert all(target not in profile_ids for target in _ROADMAP_TARGETS)


def test_profile_roadmap_docs_require_source_audit_before_runtime_promotion() -> None:
    docs = (_PROJECT_ROOT / "docs" / "api.md").read_text(encoding="utf-8")
    spec = (
        _PROJECT_ROOT
        / "spec"
        / "complete"
        / "local_032"
        / "CAPTURE_PROFILE_ROADMAP_AND_SOURCE_AUDIT.md"
    ).read_text(encoding="utf-8")

    for target in _ROADMAP_TARGETS:
        assert target in docs
        assert target in spec
    assert "source audit" in docs
    assert "runtime profile promotion" in docs
    assert "audit required -> audited" in spec
    assert "experimental -> stable" in spec


def test_package_root_exports_profile_registry_api() -> None:
    assert "CaptureProfile" in ponkan.__all__
    assert "list_capture_profiles" in ponkan.__all__
    assert "get_capture_profile" in ponkan.__all__
    assert ponkan.get_capture_profile("n3dsxl") is ponkan.list_capture_profiles()[0]


def test_profile_registry_import_does_not_load_backend_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__
    unexpected_imports: list[str] = []

    def guarded_import(
        name: str,
        global_vars: dict[str, Any] | None = None,
        local_vars: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> ModuleType:
        if name.startswith(("ponkan.devices", "ponkan.transport")):
            unexpected_imports.append(name)
        return real_import(name, global_vars, local_vars, fromlist, level)

    monkeypatch.delitem(sys.modules, "ponkan.profiles", raising=False)
    monkeypatch.setattr(builtins, "__import__", guarded_import)

    profiles = importlib.import_module("ponkan.profiles")

    assert profiles.list_capture_profiles()[0].id == "n3dsxl"
    assert unexpected_imports == []
