"""N3DSXL protocol orchestration."""

from time import sleep
from typing import Protocol

from py3dscapture.capture import RawCapture
from py3dscapture.devices.n3dsxl_ftd3 import DeviceCandidate
from py3dscapture.errors import UnsupportedDevice, UnsupportedOperation
from py3dscapture.protocol.sizes import (
    N3DSXL_BULK_IN_ENDPOINT,
    N3DSXL_BULK_OUT_ENDPOINT,
    capture_size,
    video_size,
)
from py3dscapture.transport.ftd3_pipe import FTD3_COMMAND_TIMEOUT_MS

N3DSXL_CFG_WAIT_MS = 200


class N3DSXLPipe(Protocol):
    """FTD3 operations used by the N3DSXL protocol layer."""

    backend_kind: str

    def create_pipe(self) -> None:
        """Create the FTD3 command pipe."""
        ...

    def abort_pipe(self, pipe: int) -> None:
        """Abort one FTD3 pipe."""
        ...

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Set the stream pipe transfer length."""
        ...

    def read_pipe(self, pipe: int, length: int, timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS) -> bytes:
        """Read from one FTD3 pipe."""
        ...

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> int:
        """Write to one FTD3 pipe."""
        ...


class N3DSXLSessionIdentity(Protocol):
    """Opened session identity needed for raw metadata."""

    candidate: DeviceCandidate


class N3DSXLProtocol:
    """N3DSXL connect sequence over an accepted device and FTD3 pipe."""

    def __init__(self, device: N3DSXLSessionIdentity, pipe: N3DSXLPipe) -> None:
        """Create protocol orchestration for one safe device session."""
        if not isinstance(device.candidate, DeviceCandidate):
            raise UnsupportedDevice
        self.device = device
        self.pipe = pipe

    def connect(self, *, mode_3d: bool = False) -> None:
        """Run the 2D default connect and stream setup sequence."""
        if mode_3d:
            raise UnsupportedOperation

        self.pipe.create_pipe()
        self._drain_data()
        self.pipe.abort_pipe(N3DSXL_BULK_IN_ENDPOINT)
        self.pipe.create_pipe()
        self._spi_3ds_cc_stuff()
        self._load_3ds_cc_firmware(firmware_id=1)
        self._read_3ds_config_3d()
        self._set_2d_stream_pipe()

    def read_raw_frame(self, *, mode_3d: bool = False) -> RawCapture:
        """Read one raw frame after connect."""
        if mode_3d:
            raise UnsupportedOperation
        transfer_size = capture_size(mode_3d=False)
        payload = self.pipe.read_pipe(N3DSXL_BULK_IN_ENDPOINT, transfer_size)
        return RawCapture(
            model="new_3ds_xl",
            mode_3d=False,
            payload=payload,
            transferred=len(payload),
            video_size=video_size(mode_3d=False),
            capture_size=transfer_size,
            timestamp_ns=None,
            sequence=None,
            metadata={
                "product_string": self.device.candidate.product_string,
                "product_string_status": self.device.candidate.product_string_status,
                "backend_kind": self.pipe.backend_kind,
                "vid": f"0x{self.device.candidate.info.vendor_id:04x}",
                "pid": f"0x{self.device.candidate.info.product_id:04x}",
            },
        )

    def _drain_data(self) -> None:
        self._set_spi_access(enabled=True)
        self.pipe.read_pipe(N3DSXL_BULK_IN_ENDPOINT, 0x100000, timeout_ms=N3DSXL_CFG_WAIT_MS)

    def _spi_3ds_cc_stuff(self) -> None:
        self._set_spi_access(enabled=True)
        self.pipe.write_pipe(N3DSXL_BULK_OUT_ENDPOINT, bytes([0x80, 0x01, 0xAB, 0x00]))
        self.pipe.write_pipe(
            N3DSXL_BULK_OUT_ENDPOINT,
            bytes([0x90, 0x08, 0x03, 0x02, 0x00, 0x00, 0x00, 0x00]),
        )
        self.pipe.read_pipe(N3DSXL_BULK_IN_ENDPOINT, 0x10)
        self.pipe.write_pipe(N3DSXL_BULK_OUT_ENDPOINT, bytes([0x80, 0x01, 0xAB, 0x00]))
        self._set_spi_access(enabled=False)

    def _load_3ds_cc_firmware(self, *, firmware_id: int) -> None:
        firmware_to_use = min(firmware_id, 1)
        self._set_spi_access(enabled=True)
        self.pipe.write_pipe(
            N3DSXL_BULK_OUT_ENDPOINT,
            bytes([0x42 + firmware_to_use, 0x00, 0x00, 0x00]),
        )
        sleep(N3DSXL_CFG_WAIT_MS / 1000)
        self._set_spi_access(enabled=False)

    def _read_3ds_config_3d(self) -> None:
        self._set_spi_access(enabled=True)
        self.pipe.write_pipe(N3DSXL_BULK_OUT_ENDPOINT, bytes([0x98, 0x05, 0x9F, 0x00]))
        self.pipe.read_pipe(N3DSXL_BULK_IN_ENDPOINT, 0x10)
        self._set_spi_access(enabled=False)

    def _set_2d_stream_pipe(self) -> None:
        length = capture_size(mode_3d=False)
        self.pipe.set_stream_pipe(N3DSXL_BULK_IN_ENDPOINT, length)
        self.pipe.abort_pipe(N3DSXL_BULK_IN_ENDPOINT)
        self.pipe.set_stream_pipe(N3DSXL_BULK_IN_ENDPOINT, length)

    def _set_spi_access(self, *, enabled: bool) -> None:
        second_byte = 0x80 if enabled else 0x00
        self.pipe.write_pipe(N3DSXL_BULK_OUT_ENDPOINT, bytes([0x40, second_byte, 0x00, 0x00]))
