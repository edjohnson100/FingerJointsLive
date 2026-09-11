# Changelog

All notable changes to FingerJointsLive are documented here. See [README.md](README.md) for current usage and installation instructions.

## v1.5.0 — 2026-09-11

* **Fixed: dovetail taper axis on coplanar/inline splices.** Through-dovetail generation picked the taper axis by comparing raw overlap dimensions ("smaller wins"), which only holds for corner joints — an inline splice joining two panels on the same plane could pick panel thickness instead of the actual splice width. The axis is now chosen with a geometric test (is this axis flush with the original body's own bounds?) instead of a magnitude comparison, matching the approach already used for Dog Bone plunge-axis detection.
* **Colorblind-safe, per-body preview coloring:** The live preview now shades each panel's tool bodies and a faint wash over the full selected body in one of two colorblind-safe (Okabe-Ito) colors — orange for body0, blue for body1 — so it's clear at a glance which color belongs to which panel, and which panel will end up with fingers vs. notches.
* **Preview Opacity toggle (Light/Medium/Dark):** Controls how strongly the preview wash shows through on the selected bodies, so it stays visible against material appearances that are close to the preview's own orange/blue palette. Persists with the rest of your settings.

## v1.4.1 — 2026-09-07

* **Fixed: palette invisible on a second monitor.** Fusion won't draw a floating palette outside the display its own main window occupies — if the palette was last parked on a monitor that isn't the one Fusion opens on next time (a docking-station monitor that's unplugged, a laptop undocked, etc.), the saved position was still technically valid but Fusion would refuse to draw it there, making the palette appear to vanish until Fusion's window was dragged to match. The add-in now reads the real display layout and Fusion's own window position from the OS (no third-party dependencies) and remaps a saved position onto Fusion's actual display when they don't match, keeping the palette's relative position on screen.
* Added a standalone `PaletteDisplayCheck` diagnostic script (`tools/PaletteDisplayCheck/`) for troubleshooting: run it from Fusion's Scripts and Add-Ins dialog to see the detected monitor layout, Fusion's window position, and where the palette would open.

## v1.4.0 — 2026-08-13

* **Standalone Dog Bone corner relief:** A new Dogbone tab adds a post-process corner-relief operation for router-cut joints, applied to a body's real, already-cut geometry rather than baked into finger-joint generation. Pick corners by **Body** (auto-detects the router's plunge axis from the body's shape), **Face** (you specify the axis directly — useful when a body isn't globally axis-aligned), or **Edge** (pick individual corners by hand). All three modes support picking multiple bodies/faces/edges at once, and relief is applied correctly even when picks span more than one body.
* **Four relief styles:** Corner, Minimal Corner, Long Side, and Short Side — different offset conventions for how the relief circle sits against the corner's walls.
* **Gentle status feedback:** A non-blocking status line under Preview/Apply reports picks that didn't produce any relief (e.g. an edge that isn't a genuine concave corner, or a face/body with nothing to relieve), instead of failing silently or interrupting with a dialog. A hard rejection (picking an actual convex edge in Edge mode) is still called out specifically, since accepting it would silently produce wrong geometry.

## v1.3.2 — 2026-08-07

* **Version footer:** The palette now shows a name/version footer at the bottom of every tab, matching the rest of Ed's add-in fleet.
* **Accessibility (WCAG):** Button text colors are now computed per-theme for contrast instead of a hardcoded white — every bundled theme keeps legible button text. Every button, dropdown, and collapsible section header (Configuration, Close Butt Joint, Theme Manager) now shows a visible focus ring when navigating with Tab, and those section headers are keyboard-reachable for the first time. The Remove Selected Theme/Factory Reset buttons and the modal backdrop now use theme-aware colors instead of a fixed value.

## v1.3.1 — 2026-08-01

* **UI polish pass:** Removed the primary-color accent border around the palette body (added in v1.0.1) for a cleaner look — this also drops the legacy-`style.css` auto-upgrade patch that used to re-add it to older exported theme files.
* **Themes tab collapsible:** The Theme Manager section now collapses/expands like every other section in the palette, and remembers its state between sessions.

## v1.3.0 — 2026-07-29

* **Through Dovetail joints:** A new Joint Type alongside the existing Box/Finger joints — cuts real angled dovetail pins/tails instead of straight-sided fingers. Set the **Dovetail Angle** (typical range 7–14°) and use the **Reverse Taper** checkbox if a joint doesn't interlock as expected — the correct direction depends on your model's specific geometry (corner vs. an inline splice joining two coplanar panels end-to-end, which body is selected first, etc.) and isn't something the add-in can reliably infer on its own, so it's a toggle rather than automatic.
* **Manufacturing note:** a dovetail's taper varies across the panel's thickness, so the mating cut face isn't flat — this requires 3D printing or a 5-axis CNC setup; a laser cutter or 3-axis CNC cannot reproduce it. Dovetails are most useful for 3D-printed parts or for splicing two panels end-to-end when a single piece would be too large for your laser bed or stock, not as a general laser/CNC replacement for box joints.
* **Friendlier selection dialogs:** The native "Select 1st Body," "Select 2nd Body," "Select Direction," etc. dialogs now show plain-language titles instead of raw internal names like `extendTargetFace`.
* **Update Preset:** A new button overwrites the currently-selected preset with your current settings, so you no longer have to delete and re-save under the same name just to update one.
* **Reset to Defaults confirmation:** Replaced the plain browser confirmation popup with a themed in-app dialog that matches the rest of the palette.
* Existing presets and saved defaults keep working unchanged — they pick up the new Joint Type/Dovetail Angle/Reverse Taper fields at their Box-joint defaults automatically.

## v1.2.2 — 2026-07-29

* **Toolbar polish:** The command button now shows a tool clip thumbnail and description in Fusion's toolbar tooltip.
* The palette's sub-header now displays the running version number instead of a static tagline.

## v1.2.1 — 2026-07-26

* **Fixed:** A negative `Gap Between Fingers` value (used for laser kerf compensation on a tight/press fit) could leave a thin, uncut sliver of material right at the true ends of a finger/notch row — both at closed box corners and at open/interior joints (e.g. a shelf mortise-and-tenon). The outermost cut on each end of a row now always reaches the row's true boundary regardless of gap sign; positive gap values are unaffected.

## v1.2.0 — 2026-07-23

* **Extend Loop grouped as one timeline entry:** Running the Close Butt Joint loop multiple times in a row now wraps all of the extensions into a single `CFG_Extend_XXX` timeline group, instead of creating a separate group per extension — so you can delete the whole operation at once from the timeline if needed. Note: each extension is still its own native Undo step, since Fusion gives every completed selection command its own Ctrl+Z entry.
* **Reorganized palette layout:** Preview/Generate Joints now sit right below body/direction selection, and the Configuration section sits above Close Butt Joint, so the most-used controls are closer to the top.
* **Fixed:** Collapsing/expanding a section right before closing the palette could lose that change due to a save-debounce race; section collapse state now saves immediately.

## v1.1.0 — 2026-07-22

* **Close Butt Joint (Loop):** Bodies no longer need to already overlap. Pick an edge, corner, or face on the panel you want to extend (handy when the true end-cap face is tucked against its neighbor and hard to click directly), then pick the target face to extend to — the add-in creates a real extend/join feature closing the gap automatically. The command loops (select source → select target → extend → repeat) so you can close every joint on a model without re-clicking a button each time; click Cancel on either prompt to stop. A failed extension shows a warning but keeps the loop going.
* **Palette window memory:** The palette now remembers its size, position, and docking state between sessions, restoring exactly how you left it.
* **Full settings persistence:** All configuration fields and the collapsed/expanded state of each collapsible section are now continuously auto-saved and restored, not just at Generate time.

## v1.0.1 — 2026-05-03

* **Theme accent border:** All built-in and custom themes now render a subtle primary-color border around the palette body for a more polished look. Legacy `style.css` files are automatically upgraded when exported from ThemeDesigner. (Both the border and the auto-upgrade patch were later removed in v1.3.1.)

## v1.0.0 — 2026-04-26

Initial release — a live palette remix of [Florian Pommerening's original Finger Joints add-in](https://github.com/FlorianPommerening/FingerJoints), wrapping its core mathematical engine in a modeless HTML palette.

* **Persistent Live UI:** The palette docks on the side of your screen. Tweak parameters, change settings, and see results without a modal dialog blocking your view or closing after every tweak.
* **Multi-Body Selection:** Select multiple "First Bodies" and multiple "Second Bodies" at once; the add-in calculates the intersections and generates the joints for all of them.
* **Non-Destructive Live Preview:** Renders temporary "ghost" bodies on the canvas instead of computing heavy timeline features, keeping the timeline clean and tweaking fast.
* **Preset Saving:** Save favorite joint configurations as named presets directly in the palette, with a handful of sample presets included.
* **Theming Support:** Custom built-in themes to match your preferred aesthetic.
