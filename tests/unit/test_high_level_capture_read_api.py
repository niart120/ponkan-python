from collections.abc import Iterator
from typing import cast

import numpy as np
import pytest

import ponkan.capture as capture_module
from ponkan.capture import CaptureConfig, CaptureOutput, CaptureReader, open_capture
from ponkan.errors import CaptureError, DeviceNotFound, UnsupportedOperation
from ponkan.image.frame import CaptureFrame
from ponkan.streaming.stats import StreamStats


class _FakeEngineError(CaptureError):
    pass


class _FakeEngine:
    def __init__(
        self,
        frames: list[CaptureFrame] | None = None,
        *,
        error_on_process: bool = False,
    ) -> None:
        self._frames = list(frames or [])
        self.error_on_process = error_on_process
        self.start_count = 0
        self.process_count = 0
        self.stop_count = 0

    def start(self) -> None:
        self.start_count += 1

    def process_completed(self, *, limit: int | None = None) -> int:
        _ = limit
        self.process_count += 1
        if self.error_on_process:
            raise _FakeEngineError
        return 0

    def frames(self, *, max_frames: int | None = None) -> Iterator[CaptureFrame]:
        delivered = 0
        while self._frames and (max_frames is None or delivered < max_frames):
            delivered += 1
            yield self._frames.pop(0)

    def stop(self, timeout: float | None = None) -> None:
        _ = timeout
        self.stop_count += 1

    def stats(self) -> StreamStats:
        return StreamStats(submitted=self.start_count, completed=self.process_count)


class _FakeHandle:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeD3xxBackend:
    def __init__(self, candidates: tuple[object, ...] = ("candidate",)) -> None:
        self.candidates = candidates
        self.opened: list[object] = []
        self.handle = _FakeHandle()

    def iter_device_candidates(self) -> tuple[object, ...]:
        return self.candidates

    def open(self, candidate: object) -> _FakeHandle:
        self.opened.append(candidate)
        return self.handle


class _FakeProtocol:
    def __init__(self) -> None:
        self.connected_modes: list[bool] = []

    def connect(self, *, mode_3d: bool) -> None:
        self.connected_modes.append(mode_3d)


def _frame(sequence: int | None = None) -> CaptureFrame:
    top = np.zeros((240, 400, 3), dtype=np.uint8)
    bottom = np.zeros((240, 320, 3), dtype=np.uint8)
    top[:, :] = np.array([1, 2, 3], dtype=np.uint8)
    bottom[:, :] = np.array([10, 20, 30], dtype=np.uint8)
    return CaptureFrame(
        top=top,
        bottom=bottom,
        top_right=None,
        timestamp_ns=None,
        source_model="new_3ds_xl",
        mode_3d=False,
        sequence=sequence,
    )


def test_open_capture_uses_fake_opener_and_returns_reader() -> None:
    opened_configs: list[CaptureConfig] = []

    def opener(config: CaptureConfig) -> _FakeEngine:
        opened_configs.append(config)
        return _FakeEngine([_frame()])

    reader = open_capture(_opener=opener)

    assert isinstance(reader, CaptureReader)
    assert opened_configs == [CaptureConfig()]


def test_read_frame_returns_latest_queued_frame() -> None:
    engine = _FakeEngine([_frame(sequence=1), _frame(sequence=2)])
    reader = CaptureReader(engine, config=CaptureConfig(read_timeout=0))

    frame = reader.read_frame()

    assert frame is not None
    assert frame.sequence == 2
    assert engine.start_count == 1
    assert engine.process_count == 1


def test_read_frame_timeout_returns_none() -> None:
    engine = _FakeEngine()
    reader = CaptureReader(engine, config=CaptureConfig(read_timeout=0))

    assert reader.read_frame() is None
    assert engine.start_count == 1


def test_read_returns_default_vertical_mosaic() -> None:
    reader = CaptureReader(_FakeEngine([_frame()]), config=CaptureConfig(read_timeout=0))

    image = reader.read()

    assert image is not None
    assert image.shape == (480, 400, 3)
    assert image.dtype == np.uint8
    assert image[0, 0].tolist() == [1, 2, 3]
    assert image[240, 39].tolist() == [0, 0, 0]
    assert image[240, 40].tolist() == [10, 20, 30]
    assert image[240, 359].tolist() == [10, 20, 30]
    assert image[240, 360].tolist() == [0, 0, 0]


def test_read_output_selection_returns_top_and_bottom_shapes() -> None:
    top_reader = CaptureReader(_FakeEngine([_frame()]), config=CaptureConfig(read_timeout=0))
    bottom_reader = CaptureReader(_FakeEngine([_frame()]), config=CaptureConfig(read_timeout=0))

    top = top_reader.read(output=CaptureOutput.TOP)
    bottom = bottom_reader.read(output=CaptureOutput.BOTTOM)

    assert top is not None
    assert bottom is not None
    assert top.shape == (240, 400, 3)
    assert bottom.shape == (240, 320, 3)


def test_read_can_return_bgr_copy_without_mutating_frame() -> None:
    frame = _frame()
    reader = CaptureReader(_FakeEngine([frame]), config=CaptureConfig(read_timeout=0))

    image = reader.read(output=CaptureOutput.TOP, colorspace="BGR")

    assert image is not None
    assert image[0, 0].tolist() == [3, 2, 1]
    assert frame.top[0, 0].tolist() == [1, 2, 3]


def test_read_invalid_output_raises_value_error() -> None:
    reader = CaptureReader(_FakeEngine([_frame()]), config=CaptureConfig(read_timeout=0))

    with pytest.raises(ValueError, match="side"):
        reader.read(output=cast("CaptureOutput", "side"))


def test_read_propagates_capture_errors() -> None:
    reader = CaptureReader(_FakeEngine(error_on_process=True), config=CaptureConfig(read_timeout=0))

    with pytest.raises(_FakeEngineError):
        reader.read_frame()


def test_context_manager_exit_and_close_are_idempotent() -> None:
    engine = _FakeEngine([_frame()])

    with CaptureReader(engine, config=CaptureConfig(read_timeout=0)) as reader:
        assert reader.stats().submitted == 0

    reader.close()

    assert engine.stop_count == 1


def test_open_capture_rejects_mvp_out_of_scope_config() -> None:
    with pytest.raises(UnsupportedOperation):
        open_capture(config=CaptureConfig(mode_3d=True), _opener=lambda _config: _FakeEngine())


def test_open_capture_rejects_invalid_config_values() -> None:
    with pytest.raises(ValueError, match="raw_slots"):
        open_capture(config=CaptureConfig(raw_slots=0), _opener=lambda _config: _FakeEngine())


def test_open_capture_can_override_config_read_timeout_to_none() -> None:
    opened_configs: list[CaptureConfig] = []

    def opener(config: CaptureConfig) -> _FakeEngine:
        opened_configs.append(config)
        return _FakeEngine()

    open_capture(config=CaptureConfig(read_timeout=0.5), read_timeout=None, _opener=opener)

    assert opened_configs[0].read_timeout is None


def test_default_opener_builds_d3xx_streaming_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _FakeD3xxBackend()
    protocol = _FakeProtocol()
    async_backends: list[object] = []
    engine_configs: list[CaptureConfig] = []

    monkeypatch.setattr(capture_module, "_new_d3xx_backend", lambda: backend)
    monkeypatch.setattr(capture_module, "_new_n3dsxl_protocol", lambda _handle: protocol)

    def new_async_backend(handle: object) -> object:
        async_backends.append(handle)
        return object()

    def new_engine(async_backend: object, config: CaptureConfig) -> _FakeEngine:
        _ = async_backend
        engine_configs.append(config)
        return _FakeEngine([_frame()])

    monkeypatch.setattr(capture_module, "_new_d3xx_backend_async", new_async_backend)
    monkeypatch.setattr(capture_module, "_new_streaming_engine", new_engine)

    reader = open_capture(backend="d3xx")

    assert isinstance(reader, CaptureReader)
    assert backend.opened == ["candidate"]
    assert protocol.connected_modes == [False]
    assert async_backends == [backend.handle]
    assert engine_configs == [reader.config]


def test_explicit_d3xx_native_uses_native_backend_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _FakeD3xxBackend()
    protocol = _FakeProtocol()
    native_calls: list[tuple[object, int]] = []

    monkeypatch.setattr(capture_module, "_new_d3xx_backend", lambda: backend)
    monkeypatch.setattr(capture_module, "_new_n3dsxl_protocol", lambda _handle: protocol)

    def new_native_backend(handle: object, config: CaptureConfig) -> object:
        native_calls.append((handle, config.raw_slots))
        raise _FakeEngineError

    monkeypatch.setattr(capture_module, "_new_d3xx_native_backend", new_native_backend)

    with pytest.raises(_FakeEngineError):
        open_capture(backend="d3xx-native")

    assert native_calls == [(backend.handle, 2)]
    assert backend.handle.closed


def test_default_opener_reports_device_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capture_module, "_new_d3xx_backend", lambda: _FakeD3xxBackend(()))

    with pytest.raises(DeviceNotFound):
        open_capture(backend="d3xx")


def test_explicit_libusb_backend_is_not_silently_mapped_to_d3xx() -> None:
    with pytest.raises(UnsupportedOperation):
        open_capture(backend="libusb")


def test_opencv_property_api_is_not_added() -> None:
    assert not hasattr(CaptureReader, "get")
    assert not hasattr(CaptureReader, "set")
    assert not hasattr(CaptureReader, "CAP_PROP_FRAME_WIDTH")
