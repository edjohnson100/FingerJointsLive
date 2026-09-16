# Finger Joints Live — User Guide

**Version 1.4.0 · A Fusion add-in for box joints, dovetails (through and coplanar), and CNC corner relief**

---

## 1. What this add-in does

Finger Joints Live cuts interlocking joints into two sets of solid bodies that **overlap each other in 3D**. You model your panels so they intersect, tell the add-in which bodies get the *fingers* and which get the *notches*, and it cuts matching teeth into both sides so the parts slot together.

It works from a **docked palette** that stays open while you work, rather than a modal dialog that closes after every change. Parameters update a live ghost preview in the viewport; nothing is written to the timeline until you press **Generate Joints**.

Three things live in the palette:

| Tab | What it's for |
|---|---|
| **Joints** | Box/finger joints, through dovetails, and the Close Butt Joint helper |
| **Dogbone** | Corner-relief circles for parts you'll cut on a CNC router |
| **Themes** | Appearance of the palette itself |

### What it needs from your model

- **Two solid bodies that physically overlap.** The joint is generated from the intersection volume of the two bodies. Bodies that merely touch — or that have a gap — produce nothing. (The **Close Butt Joint** tool exists to fix exactly that case; see §6.)
- **A parametric design.** The add-in temporarily switches the design to Parametric mode while it creates features and restores your previous setting afterwards.

### Who it's for

Anyone building laser-cut, CNC-routed, or 3D-printed boxes, enclosures, drawers, or panel assemblies who wants finger joints generated from geometry rather than sketched by hand.

> 🖼️ *Screenshot — Hero shot: full palette docked beside a real box-joint model, all three tabs visible in the tab strip. (pending)*

---

## 2. Installation

The add-in is a folder of Python and HTML files — there is nothing to compile or install beyond copying it into place.

1. **Download and unzip.** The folder must be named exactly `FingerJointsLive`. If you downloaded the source ZIP from the repository's main branch, the folder will be called `FingerJointsLive-main` — rename it and remove the `-main` suffix, or Fusion will not load it correctly. Release ZIPs are already named correctly.

2. **Put it where Fusion looks for add-ins.**

   - **Windows:** `%appdata%\Autodesk\Autodesk Fusion 360\API\Addins`
   - **macOS:** `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/Addins`

   Both paths are hidden by default. On Windows, paste the path into the File Explorer address bar. On macOS, use Finder's **Go → Go to Folder** (`Cmd+Shift+G`).

   *Alternatively*, keep the folder anywhere you like and add it manually in step 3 with the **+** button → *Script or add-in from device*.

3. **Run it.** In Fusion, press `Shift+S` to open **Scripts and Add-Ins**, select the **Add-Ins** tab, choose **FingerJointsLive**, and click **Run**. Tick **Run on Startup** if you want it loaded automatically with Fusion.

4. **Find the button.** The add-in adds a **Finger Joints Live** button to the **SOLID → MODIFY** panel (promoted, so it's visible without opening the dropdown). Click it to open the palette.

### Updating

Stop the add-in in **Scripts and Add-Ins**, replace the folder, and Run again. Your saved presets travel with the folder in `presets.json` — back that file up before overwriting if you have presets you care about.

---

## 3. Quick start — your first box joint

1. Model two panels so they **overlap** at the corner (e.g. each panel runs past the other by its own thickness).
2. Open the palette from **SOLID → MODIFY → Finger Joints Live**.
3. Click **Select 1st Body/Bodies**, pick the panel(s) that should end up with **fingers**, click **OK**.
4. Click **Select 2nd Body/Bodies**, pick the panel(s) that should end up with **notches**, click **OK**.
5. Leave **Select Direction** on *Auto*.
6. A color-coded ghost of the result appears in the viewport — **blue** for whatever will end up as 1st Body material, **orange** for 2nd Body. Adjust **Size Mode**, **Placement**, and sizes in the **Configuration** section — the preview follows about half a second after you stop typing.
7. Click **Generate Joints**.

Both bodies are now cut, and the new features appear in the timeline grouped as `CFG_Joint_001`. A single `Ctrl+Z` undoes the whole operation.

> **Tip:** Selection buttons turn a highlighted color once something is picked, and show the count in parentheses — e.g. `Select 1st Body/Bodies (2)`. Automatic preview only starts once *both* body selections are non-empty.

> 🖼️ *Screenshot — Step 1: two panels modeled to overlap at the corner, before any joint is generated. (pending)*
>
> 🖼️ *Screenshot — Steps 3–4: both selection buttons after picking, showing the highlighted state and `(n)` count badge. (pending)*
>
> 🖼️ *Screenshot — Step 6: the blue/orange color-coded ghost preview in the viewport. (pending)*
>
> 🖼️ *Screenshot — Step 7: the finished cut, with the timeline showing the new `CFG_Joint_001` group. (pending)*

---

## 4. The Joints tab

### 4.1 Selections

| Button | Meaning |
|---|---|
| **Select 1st Body/Bodies** | The bodies that receive **fingers** (the protruding teeth). Shown in **blue** in the preview. Multi-select allowed. |
| **Select 2nd Body/Bodies** | The bodies that receive **notches** (the slots). Shown in **orange** in the preview. Multi-select allowed. |
| **Select Direction** | Optional. A linear edge or sketch line defining which way the row of teeth runs. Leave empty to auto-detect. |
| **Clear Picks** | Clears all three selections at once. |
| **Help** | A short reminder of the three selections above. |

**Multi-select behavior.** Every 1st body is paired against every 2nd body. Pairs that don't overlap are skipped silently, so you can select all four walls of a box in two clicks (two opposite walls as 1st, two as 2nd) and let the add-in work out which pairs actually intersect. All cuts on a given body are merged into one cutting tool, so each body ends up with a single pair of timeline features regardless of how many partners it joins to.

**Direction (Auto).** With no edge picked, the add-in uses the **longest linear edge of the overlap volume** as the row direction. That is usually right. Pick an edge explicitly when the overlap is squarish and auto-detection guesses the wrong axis, or when you want the teeth running across the short dimension.

**Re-opening a selection.** Clicking a selection button again re-opens Fusion's picker with your previous picks already loaded, so you can add or remove without starting over. Clicking **OK** with nothing selected clears that selection.

> 🖼️ *Screenshot — Selections section: 1st/2nd Body buttons and Select Direction, before and after picking. (pending)*
>
> 🖼️ *Screenshot — Multi-select example: two opposite walls picked as 1st Body, two adjoining walls as 2nd Body, on a four-sided box. (pending)*

### 4.2 Preview and Generate

- **Preview** — draws a live, color-coded ghost of the result in the viewport: **blue** marks whatever will end up as **1st Body** material, **orange** marks **2nd Body** material. You'll see this two ways at once — a faint wash across each *entire* body, so it's obvious which is which without hunting for the seam, and a more solid color right at the joint itself, showing exactly how the teeth will interlock. These are *custom graphics*: not real geometry, absent from the timeline, and cleared when you press Generate, close the palette, or stop the add-in.
- **Generate Joints** — creates real, permanent features.

Auto-preview re-runs about 500 ms after you stop changing a value. While you're mid-typing an incomplete number (`0.`, `-`, an empty field), that preview tick is skipped silently and picks up again once the value is valid. Pressing **Generate** with an invalid value shows a message asking you to fix it.

> 🖼️ *Screenshot — Close-up of the color-coded ghost preview: blue and orange teeth interlocking at the seam, with the fainter blue/orange wash visible across each full body behind them. (pending)*
>
> 🖼️ *Screenshot — Legend callout on the same preview: "blue = 1st Body" and "orange = 2nd Body" labels pointing at each. (pending)*

### 4.3 Configuration reference

#### Joint Type

- **Box / Finger** — straight-sided teeth. Cuttable on a laser, waterjet, 3-axis CNC, or 3D printer.
- **Through Dovetail** — angled teeth, tapered through the panel's thickness. **Not** laser/CNC-cuttable — see §5.1.
- **Coplanar Dovetail** — the same angled teeth, but tapered across the joint's reach depth instead of the thickness, so the cut stays a constant, straight-through shape. Laser/CNC-cuttable — see §5.2.

> 🖼️ *Screenshot — Joint Type: Box, Through Dovetail, and Coplanar Dovetail, same two panels, side by side. (pending)*

#### Dovetail Angle *(dovetail only — Through and Coplanar)*
Taper angle of the pins/tails. Typical range **7°–14°**. Enter with units: `10 deg`.

> 🖼️ *Screenshot — Dovetail Angle: same joint at a shallow angle (7°) vs. a steep angle (14°). (pending)*

#### Reverse Taper *(dovetail only — Through and Coplanar)*
Flips which face of the panel is the wide end of the taper. A corner joint and an inline splice generally need **opposite** settings. If a dovetail previews as non-interlocking or won't assemble, toggle this first.

> 🖼️ *Screenshot — Reverse Taper: the same dovetail joint in both toggle states. (pending)*

#### Placement
Where the row starts and ends:

| Option | Result |
|---|---|
| **Fingers outside** | A finger at both ends of the row (one more finger than notch) |
| **Notches outside** | A notch at both ends of the row (one more notch than finger) |
| **Start w/ finger** | Equal counts, finger at the start end |
| **Start w/ notch** | Equal counts, notch at the start end |

For a closed box corner this is aesthetic. For an interior/T-junction joint it matters — see §9.

> 🖼️ *Screenshot — Placement: all four options (Fingers outside / Notches outside / Start w/ finger / Start w/ notch) on the same joint. (pending)*

#### Size Mode
How tooth widths are decided:

| Option | Behavior | Fields shown |
|---|---|---|
| **Equal Size** | Fingers and notches all the same width; count derived from **Minimal Finger Size** | Minimal Finger Size |
| **Fixed Notch** | Notches exactly the size you give; fingers absorb the remainder | Notch Size, Minimal Finger Size |
| **Fixed Finger** | Fingers exactly the size you give; notches absorb the remainder | Finger Size, Minimal Notch Size |

The "Minimal …" values are **not** the final size — they set how small a tooth is allowed to get, which is what determines how many teeth fit across the joint. The add-in fits the largest whole number of teeth that respects the minimum, then divides the length evenly among them. A larger minimum means fewer, wider teeth.

> 🖼️ *Screenshot — Size Mode: Equal Size, Fixed Notch, and Fixed Finger on the same joint length. (pending)*

#### Fixed Number of Fingers
Tick this to pin the count instead of deriving it. **Number of Fingers** then appears and the "Minimal …" fields disappear — with the count fixed, sizes are computed from the joint length directly.

> 🖼️ *Screenshot — Fixed Number of Fingers: checkbox unchecked (Minimal Finger Size shown) vs. checked (Number of Fingers shown). (pending)*

#### Gap Between Fingers (Kerf Comp.)
Clearance at every tooth-to-tooth boundary.

- **Positive** — looser fit, extra air between mating surfaces.
- **Zero** — nominal, mathematically exact fit.
- **Negative** — interference fit; the teeth are drawn oversized on purpose.

Negative is the **laser kerf compensation** setting. A laser removes material as it cuts, so a nominal joint comes out loose. Oversizing by roughly your kerf width brings the cut part back to a snug fit. Start near your measured kerf, then fine-tune with a test cut — the right value depends on your machine, material, and settings.

> 🖼️ *Screenshot — Gap Between Fingers: a loose (positive), nominal (zero), and interference (negative) fit, previewed side by side. (pending)*
>
> 🖼️ *Screenshot — A real laser-cut test joint before and after dialing in kerf compensation. (pending)*

#### Gap To Part *(experimental)*
A standoff between the mating faces — for example so a pin stands proud of the surrounding surface. This is a different axis from the tooth gap and is **unrelated to kerf**. Negative values are not supported. Leave at `0 mm` unless you specifically need it.

> 🖼️ *Screenshot — Gap To Part: a pin standing proud of the surrounding surface. (pending)*

> **Units:** every dimension field takes a Fusion expression, so `20 mm`, `0.75 in`, `thickness * 2`, and `10 deg` all work, following your document's unit settings.

### 4.4 Presets

The preset bar sits under the Preview/Generate buttons.

| Control | Action |
|---|---|
| **Presets** dropdown | Load a saved configuration |
| **Save** | Prompts for a name and saves the current settings |
| **Upd** | Overwrites the currently-selected preset with the current settings |
| **X** | Deletes the selected preset (with confirmation) |
| **Clear** | Resets all joint parameters to factory defaults (with confirmation) |

Presets store **joint parameters only** — not body selections and not Dogbone settings. **Clear** likewise leaves your selections and saved presets untouched.

A handful of sample presets ship with the add-in (common 20 mm and 40 mm equal-size configurations) to serve as starting points.

> 🖼️ *Screenshot — Preset bar: dropdown open showing the shipped sample presets, next to Save/Upd/X/Clear. (pending)*

---

## 5. Dovetails — read this first

Both dovetail Joint Types cut real angled pins and tails rather than straight fingers, and both are geometrically correct and will interlock. They differ in **which axis the taper runs along**, which is what determines what can physically cut them.

### 5.1 Through Dovetail

> **A Through Dovetail's taper varies across the thickness of the panel.** That means the mating cut face is *not* a flat straight-through cut. A laser cutter or a 3-axis CNC physically cannot produce it. Making one requires **3D printing** or a **5-axis** subtractive setup.

> 🖼️ *Screenshot — Diagram: a Through Dovetail pin's cross-section at two different depths, showing the taper is not a flat plane. (pending)*

Practical uses:

- **3D-printed parts**, where the tapered face costs nothing to produce.
- **Splicing panels end-to-end** — joining two coplanar panels inline when the full length exceeds your machine bed or stock size, if you're printing rather than cutting the result.

### 5.2 Coplanar Dovetail

Added for the same inline-splice use case as Through Dovetail, but tapered the other way: **across the joint's reach depth instead of across the panel's thickness.** The cut stays a constant, straight-through shape at every depth through the panel — the classic hand-cut "through dovetail" look, with the taper visible on the panel's wide face instead of its thin edge. That makes it **laser- and CNC-cuttable**, unlike Through Dovetail.

> 🖼️ *Screenshot — Coplanar Dovetail vs. Through Dovetail: the same splice, taper visible on the wide face vs. taper through the thickness, side by side. (pending)*

Coplanar Dovetail is meant specifically for **inline splices** — two coplanar panels joined end-to-end — not general corner joints. Applied to a plain corner it still produces valid geometry, but there's no meaningful "reach axis" to find there, so it falls back to the same axis choice Through Dovetail would use.

The add-in identifies the true reach axis by comparing each panel's own shape to the overlap region, not just by comparing the overlap's two side lengths against each other — so it stays correct even in a "square" splice, where the reach depth happens to exactly equal the panel's thickness. A simple bigger-vs-smaller comparison can't tell those two axes apart in that case; this can.

> 🖼️ *Screenshot — A "square" splice (reach depth = panel thickness) previewing correctly with Coplanar Dovetail. (pending)*

Practical uses:

- **Splicing panels end-to-end** for parts you'll actually cut on a laser or CNC router rather than print — the main reason to reach for this over Through Dovetail.

> 🖼️ *Screenshot — A splice made with Coplanar Dovetail, laser-cut and assembled. (pending)*

### 5.3 Common to both

Dovetails are not a general drop-in replacement for box joints on a laser or router — the taper only makes sense for a splice-style joint. Half-blind dovetails are not currently supported for either variant.

If a dovetail previews as not interlocking, toggle **Reverse Taper** — a corner joint and an inline splice need opposite settings, and the correct one can't be inferred from geometry alone. Very steep angles combined with certain sizes are rejected (the cut's own two walls would cross before reaching the far face); if Generate reports it couldn't compute the joint, reduce the angle or increase the tooth size. Coplanar Dovetail's reach axis is usually larger than Through Dovetail's thickness axis, so this rejection kicks in at correspondingly larger tooth sizes for a given angle — that's an expected consequence of tapering a bigger axis, not a bug.

> 🖼️ *Screenshot — A rejected self-intersecting dovetail (too steep for the tooth size) and the error message it produces. (pending)*

---

## 6. Close Butt Joint

Finger joints require overlapping bodies. If your panels merely **butt** against each other, there's nothing to intersect and nothing to cut. This tool extends one panel into the other to create that overlap.

1. Expand **Close Butt Joint** on the Joints tab and click **Extend Butt Joints (Loop)**.
2. **Pick the source:** an edge, corner (vertex), or face on the body you want to extend. Edges and corners are accepted because the actual end-cap face is often tucked up against its neighbor and hard to click — the add-in resolves your pick down to the correct planar face.
3. **Pick the target:** the planar face to extend *to*.
4. The add-in creates a real extrude-and-join feature closing the gap exactly, then immediately prompts for the next source.
5. The loop keeps repeating. **Cancel** either prompt (or click OK with nothing picked) to stop.

Notes:

- The extension joins only to its own body, so it won't accidentally merge with an unrelated body it happens to touch.
- All extensions from one loop run are wrapped into a single `CFG_Extend_XXX` timeline group.
- **Undo:** each extension is its own `Ctrl+Z` step, because Fusion gives every completed selection command its own undo entry. Deleting the timeline group removes them all at once.
- If the target face is on the wrong side of the source, you'll get a message and the loop continues — just re-pick.

> 🖼️ *Screenshot — Close Butt Joint loop, step by step: source pick → target pick → extended result → prompt for the next source. (pending)*
>
> 🖼️ *Screenshot — Before and after: two panels that only touch, then the same panels after Close Butt Joint, ready to be finger-jointed. (pending)*

---

## 7. The Dogbone tab

### Why you'd need this

A round router bit cannot cut a sharp interior corner — it leaves a radius, and the mating finger won't seat. **Dog bones** are small circular relief cuts placed at those corners so the bit clears them completely.

This is **only needed for CNC routing / milling**. Laser and waterjet cutting produce a kerf narrow enough not to need it.

Dog bone relief here is a **post-process**: you cut your joints first, then apply relief to the finished geometry. It is not an option baked into joint generation, which means it also works on corners that didn't come from this add-in at all.

### 7.1 Selection Mode

| Mode | How corners are chosen | Use when |
|---|---|---|
| **Body** | Auto-detects every qualifying interior corner on each picked body, guessing the router's plunge axis from the body's own bounding box (thinnest axis) | Default. Works for normal axis-aligned panels. |
| **Face** | Same auto-detection, but the plunge axis comes from each picked face's normal | The body isn't aligned to global axes and Body mode guesses wrong |
| **Edge** | You pick exactly which corner edges to relieve; no auto-detection | You want relief on specific corners only |

All three modes accept **multiple** picks, and picks may span more than one body — each body gets its own cut feature automatically.

> 🖼️ *Screenshot — Selection Mode: Body, Face, and Edge, one example pick shown for each. (pending)*

**What auto-detection accepts** (Body and Face modes): straight edges, between two planar faces, running parallel to the plunge axis, genuinely **concave**, within **Angle Tolerance** of 90°, and with both adjacent walls larger than the bit radius. Corners too small for the chosen bit are skipped.

**What Edge mode still enforces:** it skips the angle test, but it will *not* accept a **convex** edge. A convex corner isn't a dog bone candidate under any style — accepting it would silently build nonsense geometry — so those picks are rejected and reported.

> **Picking corners at a notch mouth is genuinely fiddly**: the real concave corner edge and a nearby convex edge sit right next to each other. With kerf comp nonzero, turn on hidden-edge visibility to tell them apart. With kerf comp at zero the two edges can be exactly coincident — temporarily hide the notched body so only the correct edges are pickable.

> 🖼️ *Screenshot — Close-up of a notch mouth: the true concave edge and the adjacent convex edge labeled, showing how close together they sit. (pending)*
>
> 🖼️ *Screenshot — Edge mode: a rejected convex-edge pick and the status-line message it produces. (pending)*

### 7.2 The status line

Under Preview/Apply, a non-blocking status line reports picks that produced nothing:

- an Edge-mode pick that wasn't a genuine concave corner,
- a Face-mode pick that found no corners using its normal as the plunge axis (usually means you picked an end/cap face instead of a side wall),
- a Body-mode pick with no qualifying interior corners at all.

None of these stop the operation — the other picks are still processed. Identical reasons collapse into one counted line. A pick contributing nothing isn't necessarily a mistake; a plain reference body in a multi-body selection legitimately has no joints to relieve.

A genuine *failure* to build relief geometry after valid corners were found still raises a dialog, because that's a real problem worth interrupting for.

> 🖼️ *Screenshot — The Dogbone status line showing a collapsed "N picks skipped" message under the Preview/Apply buttons. (pending)*

### 7.3 Style

All four styles place a circle of the bit's diameter; they differ in where its center sits.

| Style | Placement | Character |
|---|---|---|
| **Corner** | On the corner bisector, inset by `radius − clearance` | The standard diagonal dog bone. Most common choice. |
| **Minimal Corner** | Same bisector, pushed *out* by `radius + interference` | Leaves material short of the corner for a tight forced fit; smaller and less visually obvious |
| **Long Side** | Offset along one wall's normal so the circle bulges into the **longer** adjacent wall | Hides the relief in the less conspicuous wall |
| **Short Side** | The reverse — bulges into the **shorter** wall | |

For Long/Short Side, the relief visibly bulges along **one** wall rather than cutting diagonally into the corner. If a corner's walls can't be measured (a stepped or already-relieved boundary), that single corner falls back to Corner style rather than failing the whole operation.

> 🖼️ *Screenshot — Style comparison: Corner, Minimal Corner, Long Side, and Short Side relief applied to the same corner. (pending)*

### 7.4 Parameters

| Field | Default | Meaning |
|---|---|---|
| **Router Bit Diameter** | `3 mm` | Diameter of the bit you'll actually cut with. The relief radius is half this. |
| **Clearance** | `0.1 mm` | Safety margin pushing each circle slightly *past* the exact corner. Without it, a circle placed to exactly touch the corner can compute as marginally short due to floating-point rounding, which some CAM tool-path generators reject as a feature smaller than the bit. |
| **Interference** | `0.05 mm` | *Minimal Corner only.* How much material is deliberately left short of the corner, for a tight forced fit. |
| **Angle Tolerance** | `5 deg` | How close to 90° a corner must be to qualify. *Body/Face auto-detection only* — Edge mode ignores it. |

### 7.5 Applying

**Preview** shows the relief cylinders as translucent yellow ghost geometry with red edges. (Unlike the Joints tab, there's only one tool per relieved corner, so there's no second body to distinguish with a second color.) **Apply Dog Bones** creates the real cut. Features are grouped in the timeline as `CFG_DogBone_XXX` and undo as a single `Ctrl+Z`.

If one body in a multi-body selection can't be relieved, the others still are — you'll get a summary naming what succeeded and what didn't.

> 🖼️ *Screenshot — Dogbone Preview (ghost cylinders) next to the committed Apply result, on a router-cut corner. (pending)*

---

## 8. The Themes tab

Purely cosmetic — it changes the palette's own appearance, never your model.

- **Theme dropdown** (top-right of the palette, on every tab) — switch between bundled themes: Default Light, Classic Dark, Classic Light, EdJ Dark, Gruvbox Light, Hacker, Hot Pink, plus anything you've imported.
- **Font Family / Base Font Size** — adjust the active theme's typography.
- **Import / Export** — themes move as either `.css` or `.json` files, so you can share them or edit them externally.
- **Remove Selected Theme** — deletes an imported theme (enabled only for custom themes, not bundled ones).
- **Factory Reset Theme Cache** — clears all imported themes and returns to the bundled set.

Imported themes are stored in the palette's browser storage, not in your Fusion document.

> 🖼️ *Screenshot — Themes tab: theme dropdown open, plus two or three bundled themes applied to the same palette. (pending)*

---

## 9. How your work is saved

| What | Where | When |
|---|---|---|
| Joint parameters, collapsed sections, palette size/position/docking, active theme | `defaults.json` in the add-in folder | Auto-saved continuously (~½ s after any change), and on Generate |
| Dogbone parameters | `dogbone_defaults.json` | Auto-saved on any Dogbone change and on Apply |
| Named presets | `presets.json` | Only when you Save / Update / Delete |
| Last-used settings **for this document** | Fusion document attributes | Saved on Generate; reloaded when you next open the palette with that document active |

Because settings are stored per-document as well as globally, re-opening a design you generated joints in earlier restores the settings you used there, overriding the global defaults.

**Selections are never persisted** — bodies, faces, edges, and direction are cleared when the add-in stops.

### Timeline and undo

| Operation | Timeline group | Feature names | Undo |
|---|---|---|---|
| Generate Joints | `CFG_Joint_XXX` | `FJL_Fingers`, `FJL_Notches` | One `Ctrl+Z` for the entire operation |
| Apply Dog Bones | `CFG_DogBone_XXX` | `FJL_DogBones` | One `Ctrl+Z` for the entire operation |
| Extend Butt Joints | `CFG_Extend_XXX` | Extrude/join features | One `Ctrl+Z` **per extension** |

The timeline groups are organizational. Deleting a group's contents in the Fusion timeline is the way to roll back an operation by hand after you've moved on.

---

## 10. Troubleshooting

**Nothing happens when I press Generate, and there's no error.**
The bodies don't overlap. Non-overlapping pairs are skipped silently by design (that's what makes multi-select work), so if *no* pair overlaps, nothing is produced. Check that your panels genuinely intersect in 3D — or use **Close Butt Joint** to create the overlap.

**"Could not compute some joints. Double-check dimensions and overlaps."**
The requested teeth don't fit the joint length. Typically: a minimum/fixed tooth size larger than the joint itself, a fixed finger count too high for the length, or a dovetail angle steep enough that the cut walls would self-intersect. Reduce sizes/count or the angle.

**"One or more dimension fields contains an invalid value."**
A dimension field doesn't parse as a valid Fusion expression — an empty box, a stray character, or a missing unit on an angle (`10` vs `10 deg`). The live preview stays silent about this because it's a normal state while typing; Generate/Apply calls it out.

> 🖼️ *Screenshot — The "invalid value" and "could not compute some joints" message boxes, for reference. (pending)*

**The preview never appears.**
Auto-preview only runs when both body selections are populated. Press **Preview** explicitly to see the error message explaining what's missing.

**The joint is loose / too tight after cutting.**
Adjust **Gap Between Fingers**. Negative tightens (compensating for laser kerf), positive loosens. Measure your machine's actual kerf and start there, then test-cut.

**A dovetail won't assemble.**
Toggle **Reverse Taper**. Corner joints and inline splices need opposite settings.

**Face mode finds no corners.**
You most likely picked an end/cap face rather than a side wall — its normal isn't a valid plunge axis. The status line says so. Pick a side wall, or use Body mode.

**An edge I picked for a dog bone got skipped.**
It's a convex or flat edge, not a concave corner. At a notch mouth these sit side by side; see the picking tip in §7.1.

**The palette is blank or stale after I changed something.**
Stop and Run the add-in from **Scripts and Add-Ins** (`Shift+S`).

---

## 11. Known limitations

- **Through Dovetail is not laser/3-axis-CNC cuttable; Coplanar Dovetail is.** See §5. Half-blind dovetails are not supported for either variant.
- **Coplanar Dovetail is meant for inline splices, not corners.** Applied to a plain corner it still produces valid geometry, but falls back to Through Dovetail's axis choice rather than doing anything corner-specific — see §5.2.
- **Interior (T-junction) joints with kerf compensation.** On an interior joint — a shelf mortised into a wall, as opposed to an edge-to-edge box corner — combined with a nonzero gap, only **Notches outside** placement is reliable. The other placements can leave a tooth at the row boundary without its clearance, or produce oversized cuts. For box corners, all placements behave correctly at any gap value.
- **Gap To Part** is experimental and does not accept negative values.
- Every Fusion operation runs on the main thread, so a very large multi-body selection will briefly freeze the UI while it computes.

---

## 12. Credits and license

Finger Joints Live is a palette-based remix of [Florian Pommerening's original Finger Joints add-in](https://github.com/FlorianPommerening/FingerJoints), whose mathematical engine for finger/notch distribution remains at the core of the joint generation. The live palette UI, dovetails, butt-joint closing, dog bone relief, theming, and presets are additions.

Maintained by Ed Johnson. See `CHANGELOG.md` for release history and the repository's LICENSE file for licensing terms.
