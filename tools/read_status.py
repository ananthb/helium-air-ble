#!/usr/bin/env python3
"""Read live status from a A/C through an ESPHome Bluetooth proxy.

Verified against HELM__9869 via an esp32-c3 bluetooth_proxy. Reads only -- no
control, no PIN. Decodes the 0xB003 notify stream and prints the AC's state.

    pip install aioesphomeapi
    python read_status.py <proxy-ip> <noise-psk> <AC-mac e.g. E8:8F:8E:01:98:69>

Notes that cost real time (see docs/protocol.md):
  * subscribe to advertisements BEFORE connecting, or the connection response is
    routed to whichever client subscribed first (usually Home Assistant).
  * pass feature_flags from device_info() into bluetooth_device_connect().
  * WRITE THE CCCDs EXPLICITLY (0x0100 on 0xB003, 0x0200 on 0xB004). start_notify
    alone does not enable them, and the unit then streams nothing.
  * the stream only starts after a write to 0xB002 pokes it (a STATUS_DATA
    request works). The notify value is ASCII text: "Poll:<seq>:<hexframe>".
"""
import asyncio, sys
from aioesphomeapi import APIClient

SVC="0000a00a-0000-1000-8000-00805f9b34fb"
DPID={0x01:"power",0x02:"temperature",0x04:"mode",0x05:"fan_speed",0x08:"eco",
 0x19:"sleep",0x1a:"health",0x1c:"power_draw_w",0x67:"turbo",0x69:"silent",
 0x6a:"room_temp",0x6b:"coil_temp",0x6d:"display",0x6e:"swing_v",0x6f:"swing_h",
 0x73:"defrost",0x75:"error",0x79:"passkey_ack"}
MODE={0:"dry",1:"cool",2:"auto",3:"fan",4:"heat",5:"wind",6:"wet",17:"convertible"}
FAN={0:"auto",1:"low",2:"medium",3:"high"}

def ser(cid,payload=b""):
    ln=len(payload); b=bytearray(25+ln); b[0]=0xFF
    b[1:3]=cid.to_bytes(2,"big"); b[3:5]=ln.to_bytes(2,"big"); b[5:7]=(1).to_bytes(2,"big")
    b[17:21]=ln.to_bytes(4,"big"); b[25:]=payload; return bytes(b)
STATUS_REQ=ser(500)   # command_id STATUS_DATA

def parse_tuya(hexframe):
    """55aa | ver | cmd | len(2 BE) | dp-units | checksum ; dp = dpid type len(2) val"""
    try: b=bytes.fromhex(hexframe)
    except ValueError: return []
    if len(b)<7 or b[:2]!=b"\x55\xaa": return []
    ln=int.from_bytes(b[4:6],"big"); body=b[6:6+ln]; out=[]; i=0
    while i+4<=len(body):
        dp=body[i]; typ=body[i+1]; dl=int.from_bytes(body[i+2:i+4],"big")
        val=body[i+4:i+4+dl]; out.append((dp,int.from_bytes(val,"big") if val else None)); i+=4+dl
    return out

def label(dp,n):
    if dp==0x01: return "ON" if n==0 else "OFF"
    if dp==0x02: return f"{n} C setpoint"
    if dp==0x04: return MODE.get(n,n)
    if dp==0x05: return FAN.get(n,n)
    if dp==0x6a: return f"{n} C room"
    if dp in (0x19,0x67,0x69,0x6d,0x6e,0x6f): return "on" if n else "off"
    return n

async def main(proxy, psk, mac):
    ac=int(mac.replace(":",""),16)
    cli=APIClient(proxy,6053,password="",noise_psk=psk)
    await asyncio.wait_for(cli.connect(login=True),timeout=8)
    info=await cli.device_info(); ff=info.bluetooth_proxy_feature_flags
    frames=[]; adv=None; conn=False
    try:
        adv=cli.subscribe_bluetooth_le_raw_advertisements(lambda a:None); await asyncio.sleep(1)
        await asyncio.wait_for(cli.bluetooth_device_connect(ac,lambda c,m,e:None,timeout=20,
            feature_flags=ff,has_cache=False,address_type=0),timeout=25); conn=True
        svcs=await cli.bluetooth_gatt_get_services(ac)
        H={}
        for s in svcs.services:
            if s.uuid.lower()==SVC:
                for c in s.characteristics:
                    H[c.uuid[-4:].lower()]=c.handle
                    for d in c.descriptors:
                        if d.uuid.lower().startswith("00002902"):
                            H[c.uuid[-4:].lower()+"cccd"]=d.handle
        cb=lambda h,d: frames.append(bytes(d).decode("ascii","replace").strip("\x00"))
        await cli.bluetooth_gatt_write_descriptor(ac,H["b003cccd"],b"\x01\x00")
        if "b004cccd" in H: await cli.bluetooth_gatt_write_descriptor(ac,H["b004cccd"],b"\x02\x00")
        await cli.bluetooth_gatt_start_notify(ac,H["b003"],cb)
        await cli.bluetooth_gatt_write(ac,H["b002"],STATUS_REQ,False)
        await asyncio.sleep(10)
    finally:
        try:
            if conn: await cli.bluetooth_device_disconnect(ac)
        except Exception: pass
        try:
            if adv: adv()
        except Exception: pass
        await asyncio.sleep(1); await cli.disconnect()
    latest={}
    for s in frames:
        p=s.split(":")
        if len(p)>=3 and p[0]=="Poll":
            for dp,n in parse_tuya(p[-1]): latest[dp]=n
    print(f"{len(frames)} notifications; live state:")
    for dp in sorted(latest):
        print(f"  0x{dp:02x} {DPID.get(dp,'?'):12} = {label(dp,latest[dp])}")

if __name__=="__main__":
    if len(sys.argv)!=4:
        print(__doc__); sys.exit(1)
    asyncio.run(main(sys.argv[1],sys.argv[2],sys.argv[3]))
