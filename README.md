# Finger Joints Live

**Version:** 1.5.0 &nbsp;·&nbsp; **Author:** Ed Johnson (Making With An EdJ) &nbsp;·&nbsp; [Changelog](CHANGELOG.md)

A Fusion add-in that generates finger (box) joints and dovetail joints (through and coplanar) from overlapping 3D bodies, in a persistent modeless palette with live non-destructive preview and preset management.

This is a live palette remix of the original [Finger Joints](https://github.com/FlorianPommerening/FingerJoints) add-in by Florian Pommerening — it takes his core mathematical engine and wraps it in a modern HTML palette with the workflow enhancements below. Full credit for the underlying joint math and terminology (Dynamic Sizing, Placement Types, etc.) goes to his original project.

<img src="FingerJointsLiveAppIcon.png" width="300">

---

## Features

* **Persistent Live UI:** The palette docks on the side of your screen. Tweak parameters, change settings, and see results without a modal dialog blocking your view or closing after every tweak.
* **Box and Dovetail joints:** Generate straight-sided finger joints, angled Through Dovetails, or Coplanar Dovetails from the same workflow. Through Dovetail tapers across the panel thickness (3D-print or 5-axis only — not laser/CNC-cuttable; see the [Changelog](CHANGELOG.md#v130--2026-07-29)). Coplanar Dovetail tapers across the splice-reach depth instead, keeping the cut a constant shape through the panel thickness — laser/CNC-cuttable, and intended for the same inline-splice use case (joining two coplanar panels end-to-end).
* **Multi-Body Selection:** Select multiple "First Bodies" (e.g., two opposite walls of a box) and multiple "Second Bodies" (the adjoining walls) at once. The add-in calculates the intersections and generates joints for all of them together.
* **Non-Destructive Live Preview:** Instead of computing heavy timeline features, FingerJointsLive renders temporary "ghost" bodies on the canvas. This keeps your timeline clean and makes tweaking dimensions fast. Once you're happy, hit "Generate Joints" to commit the changes to the timeline in a single undo step.
* **Close Butt Joint (Loop):** Bodies don't need to already overlap. Pick an edge, corner, or face on the panel you want to extend, then pick the target face — the add-in creates a real extend/join feature closing the gap, and loops so you can close every joint on a model without re-clicking a button each time.
* **Standalone Dog Bone relief:** A post-process corner-relief operation for router-cut joints, with Body/Face/Edge selection modes and four relief styles (Corner, Minimal Corner, Long Side, Short Side).
* **Preset Saving:** Save your favorite joint configurations as named presets directly in the palette. A handful of sample presets ship with the add-in so there's something to try right away.
* **Theming:** Built-in and custom themes, live-editable from the Themes tab.

See the [Changelog](CHANGELOG.md) for the full version history.

## Installation

### Manual Installation Options

This add-in requires a quick manual installation. You can choose to install it in Fusion's default directory or a custom folder of your choice.

#### Option 1: Install in the Default Fusion Directory
1. **Download:** Download the source code as a ZIP file and extract the `FingerJointsLive-main` folder. Rename the folder to `FingerJointsLive` (remove the `-main` suffix) — Fusion requires the folder name to match the add-in name exactly, so it won't run correctly if you skip this step.
Download the zip file using the green `Code` button above or simply click this link: [FingerJointsLive Main Branch](https://github.com/edjohnson100/FingerJointsLive/archive/refs/heads/main.zip)
*(Alternatively, grab the `FingerJointsLive-vX.Y.Z.zip` asset from the [latest Release](https://github.com/edjohnson100/FingerJointsLive/releases/latest) — its folder is already named `FingerJointsLive`, so you can skip the rename step.)*
2. **Move the Folder:** Move the entire `FingerJointsLive` folder into your native Fusion Scripts directory:
   * **Windows:** `%appdata%\Autodesk\Autodesk Fusion 360\API\Addins`
     * *Note: This path is hidden by default in Windows. Copy and paste the entire path above into the File Explorer address bar to navigate there directly, bypassing the need to toggle hidden files/folders on.*
   * **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Addins`
     * *Note: `~/Library` is hidden by default on macOS as well. In Finder, press `Cmd+Shift+G` (Go to Folder), paste the path above, and press Enter to navigate there directly. (Unverified on an actual Mac as of this writing — please confirm and adjust this note if it's not accurate.)*
3. **Open Fusion:** Press `Shift + S` to open the **Scripts and Add-Ins** dialog.
4. **Run the Script:** Make sure the **Add-ins** filter checkbox is checked. You should see **FingerJointsLive** in the list of add-ins. You may want to check the 'Run on startup' option so it automatically runs when Fusion starts. Click the **Run** icon to execute the add-in.

#### Option 2: Install in a Custom Directory
1. **Download:** Download the source code as a ZIP file and extract the `FingerJointsLive-main` folder. Rename the folder to `FingerJointsLive` (remove the `-main` suffix) — Fusion requires the folder name to match the add-in name exactly, so it won't run correctly if you skip this step.
Download the zip file using the green `Code` button above or simply click this link: [FingerJointsLive Main Branch](https://github.com/edjohnson100/FingerJointsLive/archive/refs/heads/main.zip)
*(Alternatively, grab the `FingerJointsLive-vX.Y.Z.zip` asset from the [latest Release](https://github.com/edjohnson100/FingerJointsLive/releases/latest) — its folder is already named `FingerJointsLive`, so you can skip the rename step.)*
2. **Organize:** Create a dedicated folder on your computer for your Fusion tools (e.g., `Documents\Fusion_Tools`) and move the `FingerJointsLive` folder inside it.
3. **Open Fusion:** Press `Shift + S` to open the **Scripts and Add-Ins** dialog.
4. **Add the Add-in:** Click the grey **"+"** icon next to the search box at the top of the dialog and select **Script or add-in from device**.
5. **Locate:** Navigate to your custom folder, select the `FingerJointsLive` folder, and click **Select Folder**.
6. **Run the Add-in:** Make sure the **Add-ins** filter checkbox is checked. You should see **FingerJointsLive** in the list of add-ins. You may want to check the 'Run on startup' option so it automatically runs when Fusion starts. Click the **Run** icon to execute the add-in.

## Usage

*Screenshots of the current palette UI are still pending — see the placeholder below.*

The palette has three tabs: **Joints** (create finger/dovetail joints and close butt joints), **Dogbone** (post-process corner relief for CNC routing), and **Themes** (palette appearance). It docks to either side of the Fusion window or floats freely, and remembers its size, position, and docking state between sessions.

> 🖼️ *Screenshot — Hero shot: full palette open beside a real box-joint model. (pending)*

**Joints tab:** Select the bodies that get fingers and the bodies that get notches, pick a joint type (box, through dovetail, or coplanar dovetail), placement, sizing, and kerf compensation, then hit **Generate Joints** — a live, color-coded ghost preview (blue for the 1st Body's material, orange for the 2nd Body's) updates as you type. **Close Butt Joint** extends non-overlapping panels into each other first, for the case where nothing overlaps yet. Presets let you save and reload favorite configurations.

**Dogbone tab:** A post-process that adds round relief cuts at interior corners so a CNC router bit can fully clear a square inside corner — not needed for laser/waterjet cutting. Pick bodies, faces, or exact edges, choose a relief style, and apply.

**Themes tab:** Switch between built-in themes or import your own; purely cosmetic, never touches your model.

For the full field-by-field reference — every setting, troubleshooting tips, data persistence, and known limitations, with a complete set of illustrated screenshots — see the **[User Guide](USER_GUIDE.md)**.

### Other Uses

The bodies you join don't have to be rectangular, and can overlap in multiple places. You can also use the finger-joint mechanism for a lap joint (one finger placed asymmetrically at an end) or to slice a body into layers (duplicate it so it perfectly overlaps itself, then joint the copy against the original) — see [Florian Pommerening's usage guide](https://github.com/FlorianPommerening/FingerJoints#usage) for illustrated examples of both.

## Issues

If you find any issues with this remixed add-in, please report them on this project's GitHub issue tracker.

## Contributing

Pull requests for fixes and new features are very welcome.

## License

This add-in is based on the original work by Florian Pommerening which is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

## ❤️ Support the Maker (and Lucy!)

I develop these tools to improve my own workflows and love sharing them with the community. If you find FingerJointsLive useful and want to say thanks, feel free to **[buy Lucy a dog treat on Ko-fi](https://ko-fi.com/makingwithanedj)**!

***

*Happy Making!*
*— EdJ*
