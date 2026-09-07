# Finger Joints Live

**Version:** 1.4.1 &nbsp;·&nbsp; **Author:** Ed Johnson (Making With An EdJ) &nbsp;·&nbsp; [Changelog](CHANGELOG.md)

A Fusion add-in that generates finger (box) joints and through dovetail joints from overlapping 3D bodies, in a persistent modeless palette with live non-destructive preview and preset management.

This is a live palette remix of the original [Finger Joints](https://github.com/FlorianPommerening/FingerJoints) add-in by Florian Pommerening — it takes his core mathematical engine and wraps it in a modern HTML palette with the workflow enhancements below. Full credit for the underlying joint math and terminology (Dynamic Sizing, Placement Types, etc.) goes to his original project.

<img src="FingerJointsLiveAppIcon.png" width="300">

---

## Features

* **Persistent Live UI:** The palette docks on the side of your screen. Tweak parameters, change settings, and see results without a modal dialog blocking your view or closing after every tweak.
* **Box and Dovetail joints:** Generate straight-sided finger joints or angled through dovetails from the same workflow. See the [Changelog](CHANGELOG.md#v130--2026-07-29) for the dovetail manufacturing constraints (3D-print or 5-axis only — not laser/CNC-cuttable).
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

*Screenshots of the current palette UI are still pending — see the placeholders below. Everything else in this section reflects the current UI.*

The palette has three tabs: **Joints** (create finger/dovetail joints and close butt joints), **Dogbone** (post-process corner relief for CNC routing), and **Themes** (palette appearance). It docks to either side of the Fusion window or floats freely, and remembers its size, position, and docking state between sessions.

> 🖼️ *Screenshot — Hero shot: full palette open beside a real box-joint model. (pending)*

### Joints tab

**Selections:** Click **Select 1st Body/Bodies** and pick one or more bodies to receive fingers, then **Select 2nd Body/Bodies** for the bodies that receive notches. **Select Direction** picks the edge that defines the joint's orientation — leave it on Auto and the add-in uses the longest overlapping edge. **Help** opens a quick reference for these three; **Clear Picks** resets all three selections.

**Preview / Generate Joints:** **Preview** renders temporary "ghost" bodies on the canvas — no timeline features are created, so it's fast to iterate on settings. **Generate Joints** commits the joints as real timeline features, grouped into a single `CFG_Joint_XXX` timeline group and a single Undo step no matter how many body pairs are involved.

> 🖼️ *Screenshot — Live Preview vs. Generate: ghost-body preview next to the committed result. (pending)*

**Presets:** The dropdown loads a saved preset. **Save** stores the current settings under a new name; **Upd** overwrites the currently-selected preset with the current settings; **X** deletes the selected preset; **Clear** resets all settings to factory defaults (saved presets and your current body/direction selections are unaffected).

> 🖼️ *Screenshot — Presets: save / update / load flow. (pending)*

**Configuration:**
* **Joint Type** — *Box / Finger* for straight-sided fingers, or *Through Dovetail* for angled pins/tails.
  * **Dovetail Angle** (Dovetail only) — taper angle of the pins/tails, typically 7–14°.
  * **Reverse Taper** (Dovetail only) — flips which face of the joint ends up wide vs. narrow. A closed corner and an inline splice (joining two coplanar panels end-to-end) typically need opposite settings for the teeth to interlock; if a dovetail doesn't assemble, try flipping this. See the [Changelog](CHANGELOG.md#v130--2026-07-29) for the dovetail manufacturing constraints (3D-print or 5-axis only — not laser/CNC-cuttable).

    > 🖼️ *Screenshot — Joint Type: Box vs. Dovetail side-by-side. (pending)*
    > 🖼️ *Screenshot — Reverse Taper: same dovetail joint, both toggle states. (pending)*

* **Placement** — *Fingers outside* / *Notches outside* place a finger or notch at both ends of the row; *Start w/ finger* / *Start w/ notch* place a finger (or notch) at one end and the opposite at the other.
* **Size Mode** — *Equal Size* splits the overlap into equal fingers and notches; *Fixed Notch* / *Fixed Finger* holds one size fixed and calculates the other.
* **Fixed Number of Fingers** — when checked, fixes the finger count (**Number of Fingers**) and calculates sizes from it. When unchecked, a size is fixed instead (**Notch Size** / **Finger Size**, or **Minimal Notch Size** / **Minimal Finger Size** as a dynamic minimum) and the add-in fits as many fingers as will cleanly fit along the joint.
* **Gap Between Fingers (Kerf Comp.)** — clearance (positive) or interference (negative) between fingers and notches. Doubles as laser kerf compensation: a negative value oversizes the joint before cutting so the kerf brings the fit back to snug. Start near your laser's kerf width and fine-tune from a test cut.
* **Gap To Part (Exp.)** — experimental standoff/air-gap between the joint and the surrounding parts (e.g. so a pin stands proud), unrelated to kerf compensation. Negative values aren't supported.

For the original add-in's full illustrated walkthrough of the Placement/Size Mode/Gap concepts above (the underlying math is unchanged from Florian's original), see [Florian Pommerening's usage guide](https://github.com/FlorianPommerening/FingerJoints#usage).

**Close Butt Joint:** Bodies don't need to already overlap. Click **Extend Butt Joints (Loop)**, pick an edge/corner/face on the panel to extend, then pick the target face — the add-in creates a real extend/join feature closing the gap, then loops (prompting for the next source, then target) so you can close every joint on a model without re-clicking the button. Click Cancel on either prompt to stop.

> 🖼️ *Screenshot — Close Butt Joint loop: select-source → select-target → extended-result sequence. (pending)*

### Dogbone tab

A post-process operation applied to an already-cut body's real geometry — adds round relief cuts at interior corners so a CNC router bit (which is round) can fully clear a square inside corner. Not needed for laser or waterjet cutting, which cut a true sharp corner already.

**Selection Mode** determines how corners are chosen:
* **Body** — auto-detects every qualifying interior corner on each selected body, using the body's own bounding box to guess the router's plunge axis.
* **Face** — same auto-detection, but the plunge axis comes from a picked face's normal instead. Use this when a body isn't axis-aligned and Body mode guesses the wrong axis.
* **Edge** — manually pick exactly which corner edges to relieve, bypassing auto-detection entirely.

> 🖼️ *Screenshot — Dogbone selection modes: Body, Face, Edge (one shot each). (pending)*

Depending on the mode, **Select Body/Bodies to Relieve**, **Select Face(s) to Relieve**, or **Select Corner Edges** appears — all three accept multiple picks, and picks can span more than one body. In Edge mode, watch for convex corners sitting right next to the true concave corner (easy to mix up at a finger-joint notch mouth, especially at zero kerf comp where edges can be coincident) — a picked edge that isn't a genuine concave corner is skipped automatically.

**Preview / Apply Dog Bones** work like the Joints tab's Preview/Generate: Preview renders temporary geometry, Apply commits a base+cut feature pair per affected body. The status line below the buttons reports picks that didn't produce any relief (an invalid edge pick, or a body/face with nothing to relieve) without interrupting you — a genuine geometry failure during Apply still shows a dialog.

> 🖼️ *Screenshot — Dogbone status line: example of the "some picks weren't valid" feedback. (pending)*

**Configuration:**
* **Style** — *Corner*: diagonal relief centered on the corner's bisector (most common). *Minimal Corner*: same bisector, but leaves a bit of material short of the corner (**Interference**) for a tighter, less visually obvious relief. *Long Side* / *Short Side*: offset against a single adjacent wall, bulging asymmetrically toward whichever wall is longer or shorter at that specific corner.
* **Router Bit Diameter** — diameter of the round bit you'll cut this relief with; the relief radius is derived automatically.
* **Clearance** — safety margin pushing each relief circle slightly past the exact corner, so the cut unambiguously clears it.
* **Interference** (Minimal Corner only) — how far short of the corner material is deliberately left, the opposite sign of Clearance.
* **Angle Tolerance** (Body/Face mode only) — how close to 90° two adjacent faces must be to qualify as a corner. Edge mode ignores this and relieves exactly whichever corners you pick.

> 🖼️ *Screenshot — Dogbone styles comparison: Corner / Minimal Corner / Long Side / Short Side on the same corner. (pending)*

### Themes tab

The theme dropdown in the palette header applies a theme immediately. The **Theme Manager** section lets you adjust **Font Family** and **Base Font Size** for the active theme, **import/export** a theme as `style.css` (for use with a separate Theme Designer tool) or `.json`, **remove** a selected custom (imported) theme, or **factory reset** the theme cache back to the built-in set.

> 🖼️ *Screenshot — Themes tab: theme picker plus 2–3 built-in themes applied. (pending)*

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
