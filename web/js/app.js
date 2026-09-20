// Wires the Elm ports to the Web Bluetooth client.
import { AcRemote } from "./ble.js";

const app = window.Elm.Main.init({ node: document.getElementById("app") });
const ble = new AcRemote((event) => app.ports.bleEvents.send(event));

app.ports.sendIntent.subscribe(async (intent) => {
  switch (intent.kind) {
    case "connect": await ble.connect(); break;
    case "login": await ble.login(intent.pin); break;
    case "setPower": await ble.setPower(intent.on); break;
    case "setTemp": await ble.setTemp(intent.value); break;
    case "setMode": await ble.setMode(intent.value); break;
    case "setFan": await ble.setFan(intent.value); break;
    case "setSwing": await ble.setSwing(intent.on); break;
    case "disconnect": ble.disconnect(); break;
  }
});
