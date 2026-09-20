// Wires the Elm ports to the Web Bluetooth client.
import { AcRemote } from "./ble.js";

const app = window.Elm.Main.init({ node: document.getElementById("app") });
const ble = new AcRemote((event) => app.ports.bleEvents.send(event));

app.ports.sendIntent.subscribe(async (intent) => {
  switch (intent.kind) {
    case "listDevices": await ble.listDevices(); break;
    case "addDevice": await ble.addDevice(); break;
    case "connectId": await ble.connectId(intent.id); break;
    case "removeDevice": await ble.removeDevice(intent.id); break;
    case "setPasskey": await ble.setPasskey(intent.id, intent.pin || null); break;
    case "login": await ble.login(intent.pin); break;
    case "setPower": await ble.setPower(intent.on); break;
    case "setTemp": await ble.setTemp(intent.value); break;
    case "setMode": await ble.setMode(intent.value); break;
    case "setFan": await ble.setFan(intent.value); break;
    case "setSwing": await ble.setSwing(intent.on); break;
    case "setSwingH": await ble.setSwingH(intent.on); break;
    case "setOffTimer": await ble.setOffTimer(intent.value); break;
    case "setOnTimer": await ble.setOnTimer(intent.value); break;
    case "disconnect": ble.disconnect(); break;
  }
});

// Populate the saved-device list on load.
ble.listDevices();
