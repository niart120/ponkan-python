# ruff: noqa: N802
from dataclasses import dataclass

import pytest

import py3dscapture.transport.d3xx_backend as d3xx_backend
from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate
from py3dscapture.errors import OptionalDependencyError
from py3dscapture.transport.d3xx_backend import D3xxBackend


@dataclass(frozen=True, slots=True)
class _FakeD3xxInfo:
    ID: int
    Description: str | None
    SerialNumber: str | None
    Flags: int = 0


class _FakeD3xxBinding:
    def __init__(self) -> None:
        self.detail_indexes: list[int] = []
        self.created: list[tuple[object, int, _FakeD3xxInfo]] = []
        self.closed: list[_FakeD3xxInfo] = []

    def FT_CreateDeviceInfoList(self) -> tuple[int, int]:
        return 0, 3

    def FT_GetDeviceInfoDetail(self, index: int) -> tuple[int, _FakeD3xxInfo]:
        self.detail_indexes.append(index)
        if index == 0:
            return 0, _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")
        if index == 1:
            return 0, _FakeD3xxInfo(0x0403601E, "FTDI SuperSpeed-FIFO Bridge", "FT600")
        return 0, _FakeD3xxInfo(0x0403601E, None, None)

    def FT_Create(self, identifier: object, open_flag: int, device: object) -> int:
        if not isinstance(device, _FakeD3xxInfo):
            raise TypeError
        self.created.append((identifier, open_flag, device))
        return 0

    def FT_Close(self, device: object) -> int:
        if not isinstance(device, _FakeD3xxInfo):
            raise TypeError
        self.closed.append(device)
        return 0


def test_d3xx_binding_fake_lists_n3dsxl_candidate() -> None:
    binding = _FakeD3xxBinding()

    candidates = D3xxBackend(binding).iter_device_candidates()

    assert binding.detail_indexes == [0, 1, 2]
    assert len(candidates) == 2
    assert isinstance(candidates[0].candidate, DeviceCandidate)
    assert candidates[0].candidate.info.vendor_id == 0x0403
    assert candidates[0].candidate.info.product_id == 0x601E
    assert candidates[0].candidate.product_string == "N3DSXL.2"
    assert candidates[0].candidate.product_string_status == "accepted"
    assert candidates[0].index == 0
    assert candidates[1].candidate.product_string is None
    assert candidates[1].candidate.product_string_status == "unreadable"
    assert candidates[1].index == 2


def test_d3xx_open_uses_initialized_detail_and_close_is_idempotent() -> None:
    binding = _FakeD3xxBinding()
    backend = D3xxBackend(binding)
    candidate = backend.iter_device_candidates()[0]
    binding.detail_indexes.clear()

    handle = backend.open(candidate)
    handle.close()
    handle.close()

    assert binding.detail_indexes == [0]
    assert binding.created == [(0, 0x10, _FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228"))]
    assert binding.closed == [_FakeD3xxInfo(0x0403601E, "N3DSXL.2", "NXL530228")]


def test_pyd3xx_binding_missing_reports_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_module(module_name: str) -> object:
        _ = module_name
        raise ImportError

    monkeypatch.setattr(d3xx_backend, "import_module", missing_module)

    with pytest.raises(OptionalDependencyError):
        d3xx_backend.load_pyd3xx_binding()
