# Finger Joints Live

**Version:** 1.2.0

**Author:** Ed Johnson (Making With An EdJ)

This is a live palette remix of the original Finger Joints add-in created by Florian Pommerening. You can find his original repository here: [FlorianPommerening/FingerJoints](https://github.com/FlorianPommerening/FingerJoints).

This "Live" version takes the core mathematical engine of Florian's original add-in and wraps it in a modern, modeless HTML palette with several workflow enhancements.

<img src="FingerJointsLiveAppIcon.png" width="300">

---
## ✨ What's New in v1.2.0

* **Extend Loop grouped as one timeline entry:** Running the Close Butt Joint loop multiple times in a row now wraps all of the extensions into a single `CFG_Extend_XXX` timeline group in the timeline, instead of creating a separate group per extension — so you can delete the whole operation at once from the timeline if needed. Note: each extension is still its own native Undo step, since Fusion gives every completed selection command its own Ctrl+Z entry.
* **Reorganized palette layout:** Preview/Generate Joints now sit right below body/direction selection, and the Configuration section sits above Close Butt Joint, so the most-used controls are closer to the top.
* **Fixed:** Collapsing/expanding a section right before closing the palette could lose that change due to a save-debounce race; section collapse state now saves immediately.

## ✨ What's New in v1.1.0

* **Close Butt Joint (Loop):** Bodies no longer need to already overlap. Pick an edge, corner, or face on the panel you want to extend (handy when the true end-cap face is tucked against its neighbor and hard to click directly), then pick the target face to extend to — the add-in creates a real extend/join feature closing the gap automatically. The command loops (select source → select target → extend → repeat) so you can close every joint on a model without re-clicking a button each time; click Cancel on either prompt to stop. A failed extension shows a warning but keeps the loop going.
* **Palette window memory:** The palette now remembers its size, position, and docking state between sessions, restoring exactly how you left it.
* **Full settings persistence:** All configuration fields and the collapsed/expanded state of each collapsible section are now continuously auto-saved and restored, not just at Generate time.

## ✨ What's New in v1.0.1

* **Theme accent border:** All built-in and custom themes now render a subtle primary-color border around the palette body for a more polished look. Legacy `style.css` files are automatically upgraded when exported from ThemeDesigner.

## Installation

### Manual Installation Options

This script requires a quick manual installation. You can choose to install it in Fusion's default scripts directory or a custom folder of your choice.

#### Option 1: Install in the Default Fusion Directory
1. **Download:** Download the source code as a ZIP file using the green `Code` button above, or simply click this link: [Finger Joints Live Main Branch](https://github.com/edjohnson100/FingerJointsLive/archive/refs/heads/main.zip)
2. **Extract and Rename:** Extract the ZIP. The extracted folder will be named `FingerJointsLive-main`, **not** `FingerJointsLive` — GitHub always appends the branch or version name to the repo name like this. Rename the folder to exactly `FingerJointsLive` (Fusion will not recognize the add-in otherwise).
3. **Move the Folder:** Move the entire `FingerJointsLive` folder into your native Fusion Scripts directory:
   * **Windows:** `%appdata%\Autodesk\Autodesk Fusion 360\API\Addins`
   * **Mac:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Addins`
4. **Open Fusion:** Press `Shift + S` to open the **Scripts and Add-Ins** dialog.
5. **Run the Script:** Make sure the **Add-ins** filter checkbox is checked. You should see **FingerJointsLive** in the list of add-ins. You may want to check the 'Run on startup' option so it automatically runs when Fusion starts. Click the **Run** icon to execute the add-in.

#### Option 2: Install in a Custom Directory
1. **Download:** Download the source code as a ZIP file using the green `Code` button above, or simply click this link: [Finger Joints Live Main Branch](https://github.com/edjohnson100/FingerJointsLive/archive/refs/heads/main.zip)
2. **Extract and Rename:** Extract the ZIP. The extracted folder will be named `FingerJointsLive-main`, **not** `FingerJointsLive` — GitHub always appends the branch or version name to the repo name like this. Rename the folder to exactly `FingerJointsLive` (Fusion will not recognize the add-in otherwise).
3. **Organize:** Create a dedicated folder on your computer for your Fusion tools (e.g., `Documents\Fusion_Tools`) and move the `FingerJointsLive` folder inside it.
4. **Open Fusion:** Press `Shift + S` to open the **Scripts and Add-Ins** dialog.
5. **Add the Add-in:** Click the grey **"+"** icon next to the search box at the top of the dialog and select **Script or add-in from device**.
6. **Locate:** Navigate to your custom folder, select the `FingerJointsLive` folder, and click **Select Folder**.
7. **Run the Add-in:** Make sure the **Add-ins** filter checkbox is checked. You should now see **FingerJointsLive** listed. You may want to check the 'Run on startup' option so it automatically runs when Fusion starts. Click the **Run** icon to execute the add-in.

## ✨ What's New in FingerJointsLive (The Remix)

* **Persistent Live UI:** The palette docks on the side of your screen. You can tweak parameters, change settings, and see results without a modal dialog blocking your view or closing after every tweak.
* **Multi-Body Selection:** You are no longer limited to joining just two bodies at a time! You can now select multiple "First Bodies" (e.g., two opposite walls of a box) and multiple "Second Bodies" (the adjoining walls). The add-in will calculate the intersections and generate the joints for all of them at once.
* **Non-Destructive Live Preview:** Instead of computing heavy timeline features to show a preview, FingerJointsLive renders temporary "ghost" bodies on the canvas. This keeps your timeline clean and makes tweaking dimensions lightning-fast. Once you are happy with the preview, hit "Generate Finger Joints" to commit the changes to the timeline in a single undo step.
* **Preset Saving:** Save your favorite joint configurations as named presets directly in the palette. A handful of sample presets ship with the add-in so there's something to try right away.

## Original Usage Guide (For Reference)

*Note: The following documentation and images are from Florian's original add-in. The core concepts, mathematical principles, and terminology (like Dynamic Sizing, Placement Types, etc.) still apply perfectly to this Live remix. I will be updating this section with new screenshots specific to the new UI in the future.*

![Finger joint](resources/doc/demo.png)

Select two overlapping bodies and a direction. The direction is required, so the add-in knows in which plane to cut. In most cases, you probably want an edge that runs along the joint as shown in the picture.

![Selection of body and edges](resources/doc/usage1.png)

The next setting controls whether the first body has fingers on both ends, notches on both ends, or a finger on one end and a notch on the other. In the next picture, we place three fingers on the first body with different settings, the number of fingers on the second body adjusts accordingly.

![Finger placement](resources/doc/usage2.png)

The next settings determine how the size of the overlap is distributed between fingers of the first body and fingers of the second body (as we view everything from the perspective of the first body, we call fingers of the second body "notches").

When the number of fingers is fixed, we can specify their size in three ways. In the example above, we chose to have fingers and notches of equal size. Instead, we can chose to fix the size of either fingers or notches (the other size is determined automatically). The next picture shows the effect of fixing the size of fingers or notches to 5mm.

![Fixed finger size with fixed number of fingers](resources/doc/usage3.png)

Finally, instead of fixing the number of fingers, we might want to have both fingers and notches of a certain size and place as many fingers as will fit along the joint. Fixing both sizes could lead to cases where one body ends in half a finger, so instead, we only fix either the size of fingers or notches and specify a minimal size for the other. For example, the following picture fixes the size of a finger to 9mm and uses a minimal notch size of 5mm. The height of the joint is 50mm, so using four 9mm fingers and three 5mm notches would exceed the size by 1 mm. Instead, the add-in uses three 9mm fingers and increases the size of the two notches to 11.5mm. Likewise, we could fix the size of notches and make the size of fingers dynamic, or we could require that fingers and notches have the same size.

![Dynamic finger number with fixed finger size](resources/doc/usage4.png)


Starting with version 1.1 the add-in can also add a small gap between the fingers and notches for an easier fit
of the produced parts.

![Gaps between notches and fingers](resources/doc/gaps.png)

An experimental option of adding a gap between the joint and the parts was added in version 1.2.
Currently, the gap size will not always match the entered value and might be different on both parts
if their overlap is not a square. Use at your own risk and experiment with different settings
for a useful distance.

![Gaps between fingers and parts](resources/doc/gaps2.png)

Of course, the objects you join do not have to be rectangular and can overlap in multiple places.

![General objects can be joined](resources/doc/usage5.png)
![Resulting objects](resources/doc/usage6.png)


## Other Uses

In addition to creating finger joints, the add-in can be used to create lap joints and cut pieces into slices.

### Lap Joints

To create a lap joint, start with two overlapping pieces and create a finger joint with one finger placed asymmertically on the start or end of the first body.

![Lap joint settings](resources/doc/lapjointssettings.png)
![Lap joint result](resources/doc/lapjointsresults.png)

### Slicing

This is not really by design but you can duplicate a body so it perfectly overlaps with itself, then create a finger joint between the
copy and the original. This will slice the body along your chosen axis.

![Slicing](resources/doc/slicing1.png)
![Slicing](resources/doc/slicing2.png)


## Issues

If you find any issues with this remixed add-in, please report them on this project's GitHub issue tracker.

## Contributing

Pull requests for fixes and new features are very welcome.

The add-in is currently not fully parametric in the timeline, but this live palette version aims to provide a much more interactive experience.

## License

This add-in is based on the original work by Florian Pommerening which is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
