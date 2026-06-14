"""List N3DSXL USB device candidates."""

from ponkan.devices.discovery import CaptureDeviceDiscovery, list_capture_devices
from ponkan.transport.libusb_backend import LibusbBackend


def format_device_listing(discovery: CaptureDeviceDiscovery) -> str:
    """Format candidates and rejected FTDI devices for humans.

    Args:
        discovery: Public discovery result from ``list_capture_devices``.

    Returns:
        Multi-line text containing accepted candidates and rejected FTDI-family
        devices, or a single empty-state line.
    """
    header = (
        f"profile={discovery.profile_id} "
        f"backend={discovery.resolved_backend} "
        f"status={discovery.backend_status} "
        f"reason={discovery.reason}"
    )
    if not discovery.devices:
        return f"{header}\nNo capture devices found."

    lines: list[str] = [header]
    lines.extend(
        (
            f"{device.connection_status} "
            f"id={device.id} "
            f"{_format_vid_pid(device.vendor_id, device.product_id)} "
            f"product={device.product_string or '-'} "
            f"product_status={device.product_string_status} "
            f"serial={device.serial_number or '-'} "
            f"reason={device.reason} "
            f"remediation={device.remediation or '-'}"
        )
        for device in discovery.devices
    )
    return "\n".join(lines)


def main(backend: LibusbBackend | None = None) -> int:
    """Run the device-listing CLI.

    Args:
        backend: Optional backend injection for tests. ``Usb1Backend`` is used
            when omitted.

    Returns:
        Process status code. Zero means the listing was printed.
    """
    discovery = list_capture_devices(
        backend="libusb",
        include_rejected=True,
        _libusb_backend=backend,
    )
    print(format_device_listing(discovery))
    return 0


def _format_vid_pid(vendor_id: int | None, product_id: int | None) -> str:
    if vendor_id is None or product_id is None:
        return "vidpid=-"
    return f"0x{vendor_id:04x}:0x{product_id:04x}"


if __name__ == "__main__":
    raise SystemExit(main())
