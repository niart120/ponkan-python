"""FTD3 command pipe payloads and transfer wrapper."""

from struct import pack
from typing import Final

from py3dscapture.devices.n3dsxl_ftd3 import N3DSXLDevice
from py3dscapture.errors import Ftd3CommandContext, Ftd3CommandError, UnsupportedDevice
from py3dscapture.protocol.sizes import N3DSXL_FTD3_COMMAND_PIPE_ID

FTD3_COMMAND_CREATE_PIPE_ID: Final = 0x82
FTD3_COMMAND_TIMEOUT_MS: Final = 500
FTD3_COMMAND_ABORT_ID: Final = 0
FTD3_COMMAND_RW_OPERATION_PREPARE_ID: Final = 1
FTD3_COMMAND_SET_STREAM_PIPE_ID: Final = 2
FTD3_COMMAND_CREATE_ID: Final = 3
FTD3_COMMAND_DESTROY_ID: Final = 3
FTD3_COMMAND_PAYLOAD_SIZE: Final = 20


def build_create_pipe_payload(*, command_id: int = 0) -> bytes:
    """Build the cc3dsfs create-pipe command payload.

    Args:
        command_id: Monotonic command sequence number encoded into the payload.

    Returns:
        Twenty-byte little-endian FTD3 command payload.

    Raises:
        ValueError: ``command_id`` does not fit in an unsigned 32-bit field.
    """
    return _build_ptr_payload(
        command_id=command_id,
        pipe=FTD3_COMMAND_CREATE_PIPE_ID,
        command=FTD3_COMMAND_CREATE_ID,
    )


def build_abort_pipe_payload(pipe: int, *, command_id: int = 0) -> bytes:
    """Build the cc3dsfs abort-pipe command payload.

    Args:
        pipe: Pipe ID encoded into the command payload.
        command_id: Monotonic command sequence number encoded into the payload.

    Returns:
        Twenty-byte little-endian FTD3 command payload.

    Raises:
        ValueError: ``pipe`` does not fit in an unsigned byte, or
            ``command_id`` does not fit in an unsigned 32-bit field.
    """
    return _build_ptr_payload(command_id=command_id, pipe=pipe, command=FTD3_COMMAND_ABORT_ID)


def build_destroy_pipe_payload(pipe: int, *, command_id: int = 0) -> bytes:
    """Build the cc3dsfs destroy-pipe command payload.

    Args:
        pipe: Pipe ID encoded into the command payload.
        command_id: Monotonic command sequence number encoded into the payload.

    Returns:
        Twenty-byte little-endian FTD3 command payload.

    Raises:
        ValueError: ``pipe`` does not fit in an unsigned byte, or
            ``command_id`` does not fit in an unsigned 32-bit field.
    """
    return _build_ptr_payload(command_id=command_id, pipe=pipe, command=FTD3_COMMAND_DESTROY_ID)


def build_set_stream_pipe_payload(pipe: int, length: int, *, command_id: int = 0) -> bytes:
    """Build the cc3dsfs set-stream-pipe command payload.

    Args:
        pipe: Pipe ID encoded into the command payload.
        length: Stream transfer length in bytes.
        command_id: Monotonic command sequence number encoded into the payload.

    Returns:
        Twenty-byte little-endian FTD3 command payload.

    Raises:
        ValueError: ``pipe`` does not fit in an unsigned byte, ``length`` does
            not fit in an unsigned 32-bit field, or ``command_id`` does not fit
            in an unsigned 32-bit field.
    """
    return _build_len_payload(
        command_id=command_id,
        pipe=pipe,
        command=FTD3_COMMAND_SET_STREAM_PIPE_ID,
        length=length,
    )


def build_prepare_read_payload(pipe: int, length: int, *, command_id: int = 0) -> bytes:
    """Build the cc3dsfs prepare-read command payload.

    Args:
        pipe: Pipe ID that will be read after prepare.
        length: Requested read length in bytes.
        command_id: Monotonic command sequence number encoded into the payload.

    Returns:
        Twenty-byte little-endian FTD3 command payload.

    Raises:
        ValueError: ``pipe`` does not fit in an unsigned byte, ``length`` does
            not fit in an unsigned 32-bit field, or ``command_id`` does not fit
            in an unsigned 32-bit field.
    """
    return _build_len_payload(
        command_id=command_id,
        pipe=pipe,
        command=FTD3_COMMAND_RW_OPERATION_PREPARE_ID,
        length=length,
    )


def build_prepare_write_payload(pipe: int, length: int, *, command_id: int = 0) -> bytes:
    """Build the cc3dsfs prepare-write command payload.

    Args:
        pipe: Pipe ID that will be written after prepare.
        length: Payload length in bytes.
        command_id: Monotonic command sequence number encoded into the payload.

    Returns:
        Twenty-byte little-endian FTD3 command payload.

    Raises:
        ValueError: ``pipe`` does not fit in an unsigned byte, ``length`` does
            not fit in an unsigned 32-bit field, or ``command_id`` does not fit
            in an unsigned 32-bit field.
    """
    return _build_len_payload(
        command_id=command_id,
        pipe=pipe,
        command=FTD3_COMMAND_RW_OPERATION_PREPARE_ID,
        length=length,
    )


class Ftd3Pipe:
    """FTD3 command wrapper over an accepted N3DSXL session.

    This adapter sends cc3dsfs-compatible command payloads through the dedicated
    FTD3 command pipe before bulk reads and writes.
    """

    backend_kind = "libusb"

    def __init__(self, session: N3DSXLDevice, *, first_command_id: int = 0) -> None:
        """Create a pipe wrapper for one safe N3DSXL session.

        Args:
            session: Open N3DSXL device session that owns the USB handle.
            first_command_id: First command sequence number to encode.

        Raises:
            UnsupportedDevice: ``session`` is not an ``N3DSXLDevice``.
        """
        if not isinstance(session, N3DSXLDevice):
            raise UnsupportedDevice
        self.session = session
        self._next_command_id = first_command_id

    def create_pipe(self) -> None:
        """Send the create-pipe command.

        Raises:
            Ftd3CommandError: The command pipe write fails or transfers only a
                partial payload.
        """
        self._send_command(
            command_name="create_pipe",
            pipe=FTD3_COMMAND_CREATE_PIPE_ID,
            payload=build_create_pipe_payload(command_id=self._take_command_id()),
        )

    def reconnect_after_drain(self) -> None:
        """Keep protocol compatibility; libusb path keeps the current session.

        D3XX reconnect behavior is implemented by the native fallback handle.
        """

    def abort_pipe(self, pipe: int) -> None:
        """Send cc3dsfs' abort, abort, destroy sequence for one pipe.

        Args:
            pipe: Pipe ID to abort and destroy.

        Raises:
            ValueError: ``pipe`` does not fit in an unsigned byte.
            Ftd3CommandError: Any command write fails or transfers only a
                partial payload.
        """
        self._send_command(
            command_name="abort_pipe",
            pipe=pipe,
            payload=build_abort_pipe_payload(pipe, command_id=self._take_command_id()),
        )
        self._send_command(
            command_name="abort_pipe",
            pipe=pipe,
            payload=build_abort_pipe_payload(pipe, command_id=self._take_command_id()),
        )
        self._send_command(
            command_name="destroy_pipe",
            pipe=pipe,
            payload=build_destroy_pipe_payload(pipe, command_id=self._take_command_id()),
        )

    def set_stream_pipe(self, pipe: int, length: int) -> None:
        """Send the set-stream-pipe command.

        Args:
            pipe: Pipe ID to configure for streaming reads.
            length: Transfer length in bytes.

        Raises:
            ValueError: ``pipe`` or ``length`` cannot be encoded.
            Ftd3CommandError: Command write fails or transfers only a partial
                payload.
        """
        self._send_command(
            command_name="set_stream_pipe",
            pipe=pipe,
            payload=build_set_stream_pipe_payload(
                pipe,
                length,
                command_id=self._take_command_id(),
            ),
            requested_length=length,
        )

    def read_pipe(self, pipe: int, length: int, timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS) -> bytes:
        """Prepare and read from a bulk pipe.

        Args:
            pipe: Bulk IN pipe or endpoint ID.
            length: Maximum number of bytes to read.
            timeout_ms: Bulk read timeout in milliseconds.

        Returns:
            Bytes read from the USB handle.

        Raises:
            ValueError: ``pipe`` or ``length`` cannot be encoded in the prepare
                command.
            Ftd3CommandError: Prepare or bulk read fails.
        """
        prepare = build_prepare_read_payload(pipe, length, command_id=self._take_command_id())
        self._send_command(
            command_name="prepare_read",
            pipe=pipe,
            payload=prepare,
            requested_length=length,
        )
        try:
            return self.session.handle.bulk_read(pipe, length, timeout_ms)
        except Exception as exc:
            raise Ftd3CommandError(
                Ftd3CommandContext(
                    command_name="read_pipe",
                    pipe=pipe,
                    payload_length=0,
                    requested_length=length,
                    transferred=None,
                )
            ) from exc

    def write_pipe(
        self,
        pipe: int,
        payload: bytes,
        timeout_ms: int = FTD3_COMMAND_TIMEOUT_MS,
    ) -> int:
        """Prepare and write to a bulk pipe.

        Args:
            pipe: Bulk OUT pipe or endpoint ID.
            payload: Bytes to write after prepare.
            timeout_ms: Bulk write timeout in milliseconds.

        Returns:
            Number of payload bytes transferred by the handle.

        Raises:
            ValueError: ``pipe`` or payload length cannot be encoded in the
                prepare command.
            Ftd3CommandError: Prepare or bulk write fails.
        """
        prepare = build_prepare_write_payload(
            pipe,
            len(payload),
            command_id=self._take_command_id(),
        )
        self._send_command(
            command_name="prepare_write",
            pipe=pipe,
            payload=prepare,
            requested_length=len(payload),
        )
        try:
            return self.session.handle.bulk_write(pipe, payload, timeout_ms)
        except Exception as exc:
            raise Ftd3CommandError(
                Ftd3CommandContext(
                    command_name="write_pipe",
                    pipe=pipe,
                    payload_length=len(payload),
                    requested_length=len(payload),
                    transferred=None,
                )
            ) from exc

    def _send_command(
        self,
        *,
        command_name: str,
        pipe: int,
        payload: bytes,
        requested_length: int | None = None,
    ) -> None:
        try:
            transferred = self.session.handle.bulk_write(
                N3DSXL_FTD3_COMMAND_PIPE_ID,
                payload,
                FTD3_COMMAND_TIMEOUT_MS,
            )
        except Exception as exc:
            raise Ftd3CommandError(
                Ftd3CommandContext(
                    command_name=command_name,
                    pipe=pipe,
                    payload_length=len(payload),
                    requested_length=requested_length,
                    transferred=None,
                )
            ) from exc
        if transferred != len(payload):
            raise Ftd3CommandError(
                Ftd3CommandContext(
                    command_name=command_name,
                    pipe=pipe,
                    payload_length=len(payload),
                    requested_length=requested_length,
                    transferred=transferred,
                )
            )

    def _take_command_id(self) -> int:
        command_id = self._next_command_id
        self._next_command_id += 1
        return command_id


def _build_ptr_payload(*, command_id: int, pipe: int, command: int) -> bytes:
    return _build_preamble(command_id=command_id, pipe=pipe, command=command) + pack("<QI", 0, 0)


def _build_len_payload(*, command_id: int, pipe: int, command: int, length: int) -> bytes:
    _validate_u32(length)
    return _build_preamble(command_id=command_id, pipe=pipe, command=command) + pack(
        "<IQ",
        length,
        0,
    )


def _build_preamble(*, command_id: int, pipe: int, command: int) -> bytes:
    _validate_u32(command_id)
    _validate_u8(pipe)
    _validate_u8(command)
    return pack("<IBBH", command_id, pipe, command, 0)


def _validate_u8(value: int) -> None:
    if not 0 <= value <= 0xFF:
        raise ValueError


def _validate_u32(value: int) -> None:
    if not 0 <= value <= 0xFFFFFFFF:
        raise ValueError
