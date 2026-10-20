# iPhone shortcut: Share → Puente

[Español](atajo-iphone.md)

With this shortcut you send photos and videos to your computer from the **Share** button of any app (Photos, WhatsApp, Files), without opening the Puente page. Files go to the folder currently selected on the page.

You build it once in the **Shortcuts** app, which comes with the iPhone. It takes about 5 minutes.

## Before you start

On the computer, open the Puente screen: click the icon next to the clock, or use the page that opens when Puente starts. Expand **"iPhone shortcut"** and keep the **shortcut address** and the **shortcut key** in view.

## Steps

1. Open **Shortcuts** → **Shortcuts** tab → **+**. Tap the name at the top and call it **Puente**.
2. Tap **ⓘ** and turn on **Show in Share Sheet**. In "Receive … from Share Sheet", keep only **Images** and **Media**.
3. Add **Repeat with Each**. It must say "in **Shortcut Input**".
4. Inside the repeat, add **Get Contents of URL**:
   - **URL:** the shortcut address, for example `http://192.168.1.20:8850/api/subir`.
   - Tap **›** and set **Method: POST**.
   - **Headers:**
     - `X-Puente` = `1`
     - `X-Llave` = your key
     - `X-Nombre` = **Repeat Item** → **Name**
   - **Request Body:** **File** → **Repeat Item**.
5. Below **End Repeat**, add **Show Notification** with "Sent to the computer".
6. Try it: in Photos, select some photos → **Share** → **Puente**. The first time, iOS asks whether Shortcuts may connect: tap **Always Allow**.

## If you lose your phone

Delete `llave_atajo` from `config.local.json` and restart Puente. A new key is created, the old one stops working, and every phone is signed out.

## Tip: open the Photo Library with one tap

A web page cannot open the Photo Library without iOS showing its menu first, but a shortcut can. Make another shortcut like this one that starts with **Select Photos** (turn on "Select Multiple") instead of receiving from the Share Sheet. Then add it to your Home Screen from its menu.
