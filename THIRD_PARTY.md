# Third-party code and assets

- **Realistic World Gen 2**, GT New Horizons contributors: https://github.com/GTNewHorizons/Realistic-World-Gen-2. The offline preview is downloaded separately at tag 2.0.6, commit `497fc1f49dcab6032fb828a818931e2c391ff10e`. Upstream is licensed under GNU GPL v3; see its `LICENSE.txt`. No upstream game binaries are included in this repository or release archive.
- The Java migration adapter calls upstream preview initialization and generation APIs. It includes a workaround for preview-only Thaumcraft biome registration and independently caches reused noise arrays. The adapter is GPL-3.0-or-later, like this project.
- Anvil region and NBT files are read using the project's own small implementation. Tests generate synthetic data. Minecraft, Forge, GTNH, and individual mods retain their respective licenses and trademarks; they are not distributed here.
- The interface uses system fonts and inline geometric symbols. No third-party UI libraries, remote fonts, or image assets are loaded.

The root `LICENSE` contains the GNU General Public License version 3. Project code may be used under that version or, at your option, any later version. The exact pinned upstream source is subject to its own license notice.
