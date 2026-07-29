<!--
  This README is a macOS desktop.

  The hero is one generated SVG: wallpaper, menu bar, and the Terminal window
  open on it. The Dock is deliberately NOT in that image - GitHub renders it as
  an <img>, where link traversal is off, so a dock drawn in there could never be
  clicked.

  The row under it is seven images that together make up the rest of the
  desktop: a wallpaper filler, the five dock segments, another filler. Sized in
  percentages that sum to 100, so the row spans the full width and never wraps,
  at any viewport.

  Three things below are load-bearing. Break any of them and it falls apart:

    1. NO WHITESPACE between the tags. Whitespace between inline elements
       renders as a gap and the row breaks into seven floating tiles.
    2. align="top" on every image. Without it an inline image reserves
       descender space underneath and a 6px white line opens above the row.
    3. The percentages. 33 + 6.8x5 + 33 = 100. The fillers are 369x92 native
       because (33/6.8) x (76/92) = 4.009 is the aspect that makes their height
       match the segments' at every width. Change a percentage, recompute it.
-->

<p align="center">
  <a href="https://ishraqkhan.com"><img align="top" alt="Ishraq Khan — founder and CEO of Kodezi. A macOS desktop with a terminal open, showing origin, role, languages and live GitHub statistics." src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/desktop_light.svg"></a>
  <a href="https://ishraqkhan.com"><img align="top" width="33%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock_edge_left.svg" alt=""></a><a href="https://ishraqkhan.com" title="ishraqkhan.com"><img align="top" width="6.8%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock0_globe.svg" alt="Website"></a><a href="https://kodezi.com" title="kodezi.com"><img align="top" width="6.8%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock1_kodezi.svg" alt="Kodezi"></a><a href="mailto:ishraq@kodezi.com" title="ishraq@kodezi.com"><img align="top" width="6.8%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock2_email.svg" alt="Email"></a><a href="https://www.linkedin.com/in/ishraqkhann/" title="LinkedIn"><img align="top" width="6.8%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock3_linkedin.svg" alt="LinkedIn"></a><a href="https://x.com/ishraqkhann" title="@ishraqkhann"><img align="top" width="6.8%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock4_x.svg" alt="X"></a><a href="https://ishraqkhan.com"><img align="top" width="33%" src="https://raw.githubusercontent.com/ishraqkhann/ishraqkhann/main/dock_edge_right.svg" alt=""></a>
</p>
