from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate
from py3dscapture.errors import DeviceOpenError
from py3dscapture.transport.ftd3_backend import BackendKind, open_ftd3_transport
from py3dscapture.transport.libusb_backend import UsbDeviceInfo


class _FakeLibusbHandle:
    def __init__(self) -> None:
        self.closed = False

    def detach_kernel_driver(self, interface: int) -> None:
        _ = interface

    def set_configuration(self, configuration: int) -> None:
        _ = configuration

    def claim_interface(self, interface: int) -> None:
        _ = interface

    def release_interface(self, interface: int) -> None:
        _ = interface

    def close(self) -> None:
        self.closed = True

    def bulk_write(self, endpoint: int, payload: bytes, timeout_ms: int) -> int:
        _ = endpoint, timeout_ms
        return len(payload)

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        _ = endpoint, timeout_ms
        return bytes(length)


class _FakeLibusbBackend:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.opened: list[UsbDeviceInfo] = []

    def iter_devices(self) -> list[UsbDeviceInfo]:
        return []

    def open(self, device: UsbDeviceInfo) -> _FakeLibusbHandle:
        self.opened.append(device)
        if self.error is not None:
            raise self.error
        return _FakeLibusbHandle()


class _FakeD3xxCandidate:
    pass


class _FakeD3xxHandle:
    backend_kind: BackendKind = "d3xx"

    def __init__(self) -> None:
        self.candidate = candidate()

    def close(self) -> None:
        pass

    def create_pipe(self) -> None:
        pass

    def abort_pipe(self, pipe: int) -> None:
        _ = pipe

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        _ = pipe, length

    def read_pipe(self, pipe: int, length: int, timeout_ms: int) -> bytes:
        _ = pipe, timeout_ms
        return bytes(length)

    def write_pipe(self, pipe: int, payload: bytes, timeout_ms: int) -> int:
        _ = pipe, timeout_ms
        return len(payload)

    def reconnect_after_drain(self) -> None:
        pass


class _FakeD3xxBackend:
    def __init__(self) -> None:
        self.opened: list[_FakeD3xxCandidate] = []
        self.candidate = _FakeD3xxCandidate()

    def iter_device_candidates(self) -> tuple[_FakeD3xxCandidate, ...]:
        return (self.candidate,)

    def open(self, candidate: object) -> _FakeD3xxHandle:
        if not isinstance(candidate, _FakeD3xxCandidate):
            raise TypeError
        self.opened.append(candidate)
        return _FakeD3xxHandle()


def candidate() -> DeviceCandidate:
    return DeviceCandidate(
        info=UsbDeviceInfo(
            bus_number=7,
            address=2,
            vendor_id=0x0403,
            product_id=0x601E,
            product_string=None,
            serial_number=None,
        ),
        product_string=None,
        product_string_status="unreadable",
    )


def test_libusb_success_uses_libusb_transport_without_d3xx_fallback() -> None:
    libusb_backend = _FakeLibusbBackend()
    d3xx_backend = _FakeD3xxBackend()

    transport = open_ftd3_transport(candidate(), libusb_backend, d3xx_backend)

    assert transport.backend_kind == "libusb"
    assert len(libusb_backend.opened) == 1
    assert d3xx_backend.opened == []


def test_libusb_driver_mismatch_uses_d3xx_fallback() -> None:
    libusb_backend = _FakeLibusbBackend(DeviceOpenError("LIBUSB_ERROR_NOT_FOUND [-5]"))
    d3xx_backend = _FakeD3xxBackend()

    transport = open_ftd3_transport(candidate(), libusb_backend, d3xx_backend)

    assert transport.backend_kind == "d3xx"
    assert d3xx_backend.opened == [d3xx_backend.candidate]
