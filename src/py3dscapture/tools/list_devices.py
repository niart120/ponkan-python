"""List N3DSXL USB device candidates."""

from py3dscapture.devices.n3dsxl_ftd3 import DeviceListing, list_n3dsxl_devices
from py3dscapture.transport.libusb_backend import LibusbBackend, Usb1Backend


def format_device_listing(listing: DeviceListing) -> str:
    """Format candidates and rejected FTDI devices for humans."""
    if not listing.candidates and not listing.rejected:
        return "No N3DSXL candidates or rejected FTDI devices found."

    lines: list[str] = []
    for candidate in listing.candidates:
        info = candidate.info
        lines.append(
            "candidate "
            f"{_format_location(info.bus_number, info.address)} "
            f"{_format_vid_pid(info.vendor_id, info.product_id)} "
            f"product={candidate.product_string} serial={info.serial_number or '-'}"
        )
    for rejected in listing.rejected:
        info = rejected.info
        lines.append(
            "rejected "
            f"{_format_location(info.bus_number, info.address)} "
            f"{_format_vid_pid(info.vendor_id, info.product_id)} "
            f"product={info.product_string or '-'} reason={rejected.reason}"
        )
    return "\n".join(lines)


def main(backend: LibusbBackend | None = None) -> int:
    """CLI entrypoint."""
    listing = list_n3dsxl_devices(backend or Usb1Backend())
    print(format_device_listing(listing))
    return 0


def _format_location(bus_number: int | None, address: int | None) -> str:
    bus = "-" if bus_number is None else str(bus_number)
    address_text = "-" if address is None else str(address)
    return f"bus={bus} address={address_text}"


def _format_vid_pid(vendor_id: int, product_id: int) -> str:
    return f"0x{vendor_id:04x}:0x{product_id:04x}"


if __name__ == "__main__":
    raise SystemExit(main())
