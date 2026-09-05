#!/usr/bin/env python3
"""Dump a A/C's GATT table through an ESPHome Bluetooth proxy.

The AC does not need to be near you -- any ESP32 running `bluetooth_proxy` within
BLE range of it works as a remote GATT client.

    pip install aioesphomeapi
    ./dump_gatt.py --proxy 192.168.1.50 --psk "$(cat noise_psk)" --mac E8:8F:8E:01:98:69

The PSK is the `api.encryption.key` from the proxy's ESPHome config. Omit --mac to
scan for anything advertising the the A/C service instead.

Output goes to stdout as text, and to --json as a machine-readable map.
"""
import argparse, asyncio, json, sys

from aioesphomeapi import APIClient

AC_SERVICE = "0000a00a-0000-1000-8000-00805f9b34fb"

PROPS = (("broadcast", 0x01), ("read", 0x02), ("write-no-response", 0x04),
         ("write", 0x08), ("notify", 0x10), ("indicate", 0x20),
         ("authenticated-write", 0x40), ("extended", 0x80))


def short(uuid):
    """0000b002-0000-1000-8000-00805f9b34fb -> 0xB002; leave real 128-bit alone."""
    s = str(uuid).lower()
    return "0x" + s[4:8].upper() if s.endswith("-0000-1000-8000-00805f9b34fb") else s


def hexdump(b, width=16):
    for off in range(0, len(b), width):
        chunk = b[off:off + width]
        text = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        yield "%4d  %-*s  %s" % (off, width * 3 - 1, chunk.hex(" "), text)


async def find_device(cli, timeout):
    """Return (mac_int, address_type, name) for the first A/C advertiser seen."""
    found = asyncio.get_running_loop().create_future()

    def on_adv(adv):
        if found.done():
            return
        name = (adv.name.decode(errors="replace") if isinstance(adv.name, bytes)
                else adv.name or "")
        uuids = [str(u).lower() for u in (adv.service_uuids or [])]
        if AC_SERVICE in uuids or name.startswith("HELM"):
            found.set_result((adv.address, getattr(adv, "address_type", 0), name))

    unsub = cli.subscribe_bluetooth_le_advertisements(on_adv)
    try:
        return await asyncio.wait_for(found, timeout)
    finally:
        unsub()


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--proxy", required=True, help="ESPHome proxy host or IP")
    ap.add_argument("--port", type=int, default=6053)
    ap.add_argument("--psk", required=True, help="api.encryption.key of the proxy")
    ap.add_argument("--mac", help="AC address, e.g. E8:8F:8E:01:98:69 (default: scan)")
    ap.add_argument("--address-type", type=int, default=0,
                    help="0 public, 1 random (default 0)")
    ap.add_argument("--scan-timeout", type=float, default=45.0)
    ap.add_argument("--json", help="write the map here")
    args = ap.parse_args()

    cli = APIClient(args.proxy, args.port, None, noise_psk=args.psk)
    await cli.connect(login=True)
    info = await cli.device_info()
    print("proxy: %s (ESPHome %s), BLE feature flags 0x%02X"
          % (info.name, info.esphome_version, info.bluetooth_proxy_feature_flags))

    # Subscribing is not optional. The ESP delivers BluetoothDeviceConnectionResponse
    # only to the API connection that subscribed to advertisements -- without this the
    # ESP opens the connection and we never hear about it. It also takes BLE proxying
    # away from Home Assistant for the duration, so this stays short.
    unsub = cli.subscribe_bluetooth_le_raw_advertisements(lambda r: None)
    try:
        if args.mac:
            addr, addr_type = int(args.mac.replace(":", ""), 16), args.address_type
        else:
            print("scanning for a A/C advertiser (up to %.0fs)..." % args.scan_timeout)
            addr, addr_type, name = await find_device(cli, args.scan_timeout)
            print("found %s at %012x (address type %d)" % (name, addr, addr_type))

        state, ev = {}, asyncio.Event()

        def on_conn(connected, mtu, error):
            state.update(connected=connected, mtu=mtu, error=error)
            ev.set()

        # feature_flags must be passed explicitly; it is NOT taken from device_info().
        await cli.bluetooth_device_connect(
            addr, on_conn, timeout=30, has_cache=False,
            feature_flags=info.bluetooth_proxy_feature_flags, address_type=addr_type)
        if not state.get("connected"):
            sys.exit("connect failed: error=%s" % state.get("error"))
        print("connected, MTU %s\n" % state.get("mtu"))

        out = []
        for svc in (await cli.bluetooth_gatt_get_services(addr)).services:
            print("SERVICE %s  (handle %d)" % (short(svc.uuid), svc.handle))
            for ch in svc.characteristics:
                names = ",".join(n for n, bit in PROPS if ch.properties & bit)
                print("  CHAR %s  handle=%d  props=0x%02x [%s]"
                      % (short(ch.uuid), ch.handle, ch.properties, names))
                for d in ch.descriptors:
                    print("    DESC %s  handle=%d" % (short(d.uuid), d.handle))
                value = None
                if ch.properties & 0x02:
                    try:
                        value = bytes(await cli.bluetooth_gatt_read(addr, ch.handle, timeout=10))
                        print("    READ %d bytes:" % len(value))
                        for line in hexdump(value):
                            print("      " + line)
                    except Exception as exc:
                        print("    READ failed: %s" % exc)
                out.append({
                    "service": short(svc.uuid), "characteristic": short(ch.uuid),
                    "handle": ch.handle, "properties": ch.properties,
                    "property_names": names,
                    "descriptors": [{"uuid": short(d.uuid), "handle": d.handle}
                                    for d in ch.descriptors],
                    "value": value.hex() if value else None,
                })
            print()

        if args.json:
            with open(args.json, "w") as fh:
                json.dump(out, fh, indent=2)
            print("wrote %s" % args.json)

        await cli.bluetooth_device_disconnect(addr)
    finally:
        unsub()
        # If Home Assistant shares this proxy, confirm its scanner resumed --
        # it does not always, and devices go unavailable silently when it does not.


if __name__ == "__main__":
    asyncio.run(main())
