import ctypes

import pytest

from py3dscapture.transport.d3xx_native import (
    D3xxNativeApi,
    D3xxNativeApiUnavailable,
    NativeOverlapped,
)


class _FakeFunction:
    def __init__(self, status: int = 0) -> None:
        self.status = status
        self.argtypes: list[object] | None = None
        self.restype: object | None = None
        self.calls: list[tuple[object, ...]] = []

    def __call__(self, *args: object) -> int:
        self.calls.append(args)
        return self.status


class _FakeDll:
    def __init__(self) -> None:
        self.FT_ReadPipeEx = _FakeFunction()
        self.FT_GetOverlappedResult = _FakeFunction()
        self.FT_InitializeOverlapped = _FakeFunction()
        self.FT_ReleaseOverlapped = _FakeFunction()
        self.FT_AbortPipe = _FakeFunction()
        self.FT_SetStreamPipe = _FakeFunction()


class _Provider:
    def __init__(self, dll: object | None, handle: object = ctypes.c_void_p(1234)) -> None:
        self.dll = dll
        self.handle = handle

    def pyd3xx_native_dll(self) -> object | None:
        return self.dll

    def pyd3xx_native_handle(self) -> object:
        return self.handle


def test_native_overlapped_matches_64_bit_windows_layout() -> None:
    assert ctypes.sizeof(NativeOverlapped) == 32
    assert NativeOverlapped.Internal.offset == 0
    assert NativeOverlapped.InternalHigh.offset == 8
    assert NativeOverlapped.u.offset == 16
    assert NativeOverlapped.hEvent.offset == 24


def test_native_api_requires_dll_surface() -> None:
    with pytest.raises(D3xxNativeApiUnavailable):
        D3xxNativeApi.from_pyd3xx_handle(_Provider(None))


def test_native_api_binds_function_signatures() -> None:
    dll = _FakeDll()

    api = D3xxNativeApi.from_pyd3xx_handle(_Provider(dll))

    assert api is not None
    assert dll.FT_ReadPipeEx.argtypes is not None
    assert dll.FT_ReadPipeEx.restype is not None
    assert len(dll.FT_ReadPipeEx.argtypes) == 6
    assert len(dll.FT_GetOverlappedResult.argtypes or []) == 4
    assert len(dll.FT_AbortPipe.argtypes or []) == 2


def test_native_api_reports_missing_function() -> None:
    dll = _FakeDll()
    del dll.FT_AbortPipe

    with pytest.raises(D3xxNativeApiUnavailable):
        D3xxNativeApi(dll, ctypes.c_void_p(1234))
