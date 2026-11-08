# GTNH RWG2 Migrator

**Keep your bases. Regenerate the surrounding overworld with RWG2.**

A local web wizard for GT New Horizons players moving an existing world to RWG2. Select claimed areas and waypoints, set a chunk border, choose nearby biomes, compare predicted terrain seams, then create a verified server copy and a matching Prism client.

**[Инструкция на русском →](README.ru.md)** · [Download](https://github.com/ilachev/gtnh-rwg2-migrator/releases) · [Report a problem](https://github.com/ilachev/gtnh-rwg2-migrator/issues)

## Start

1. Install **Python 3.11+**, **Git**, and a full **JDK 21**. `python3`, `git`, `java`, and `javac` must be available to the launcher. On Windows, Python's `py` launcher is supported.
2. Download and extract the latest release, or clone this repository.
3. On **macOS**, open `Start.command`. On **Windows**, open `Start.bat`. On **Linux**, run `sh Start.command` from a terminal.
4. A browser opens the wizard. Keep its terminal window open while it works. Use **EN / RU** to choose the interface language.

No Python packages need installing when running from the extracted folder. Alternatively:

```sh
git clone https://github.com/ilachev/gtnh-rwg2-migrator.git
cd gtnh-rwg2-migrator
python3 -m gtnh_migrator
```

## The five steps

1. **Source world.** Choose a stopped **GTNH 2.9.0 Java 17–26 server distribution** containing `rwg2-2.0.6.jar`. Optionally choose a Prism/MultiMC instance containing `instance.cfg` to include its matching JourneyMap waypoints and clone its client.
2. **Keep your places.** Select connected groups of Server Utilities claims. Every overworld claim group is selected initially. Choose a border in **chunks**, with one chunk equal to **16 blocks**. Optional waypoints can protect additional areas. Set a preferred biome separately for each selected claim area, or leave it blank to prioritize terrain continuity.
3. **Find generation.** See the preservation map. Build and run the official offline generator, compare candidates, and inspect estimated average and maximum seam heights. Pan and zoom the map. Biome coverage measures how many sampled points match your requested biome.
4. **Create a copy.** Choose new, non-existing output folders. Confirm that the original server and client are stopped. The wizard copies the server, creates and verifies a complete world backup, regenerates only the unselected overworld territory, and verifies preserved data before making the final folder available.
5. **Explore.** Start the copy with its generated `start-rwg2-trial.sh` or `.bat`, using Java 21. Open the new client profile and connect normally through Multiplayer. Review the world in game before adopting it.

The wizard does **not** start or stop Minecraft, edit system services, change scheduled restarts, or connect to remote servers. If yours runs on another machine, work with a stopped local copy and transfer the finished copy back. Update any service's working directory and start command when you choose to adopt the new server.

## What is preserved

- Selected overworld chunks, including buildings and block entities, retain their **original compressed Anvil records and timestamps**. Terrain inside them is not regenerated.
- **Every other dimension** is copied in full. Player data, inventories, quests, teams, and claim metadata are verified unchanged.
- A full, checked backup of the pre-migration world is written to `.migration/world-before-rwg2.tar.gz` inside the new server folder. The report includes its SHA-256.
- The original source world is read only. Full hashes detect changes during copying; a changing source is rejected.
- Existing destination folders and destinations inside the source are refused. Work happens in a separate `.partial-*` folder, which is renamed only after successful verification. If an operation fails, an incomplete folder may remain for inspection; it is not a ready server.
- With an optional client, only this server's JourneyMap overworld tiles are archived in the **new** client. Other dimension maps and waypoints remain. Matching Visual Prospecting overworld caches are archived so veins can be rediscovered.

Unselected claims are retained as metadata even though their terrain may regenerate. Overworld waypoints outside the preserved territory remain as references; their old destination may no longer exist. Inspect the selection carefully.

## What to expect from RWG2

Offsets change the placement of climates, biomes, and landmasses. They **do not perform automatic terrain blending**. The same biome and suitable offsets can make transitions look natural, but some boundaries may still contain cliffs. The map shows **sampled estimates**, not a guarantee for every block. Rivers, surface decoration, custom biome settings, and small neighboring biomes can differ from the preview.

Searching supports different world seeds and per-area biome requests; no example base coordinates or chosen offsets are built in. The preview uses the pinned [official RWG2 2.0.6 source](https://github.com/GTNewHorizons/Realistic-World-Gen-2/tree/2.0.6), commit `497fc1f49dcab6032fb828a818931e2c391ff10e`, with a separate migration adapter. It does not replace or modify the installed game JAR.

The first search downloads the upstream build dependencies and can take several minutes or longer on a slow connection. Later searches reuse `~/.cache/gtnh-rwg2-migrator`. The adapter fixes Thaumcraft preview registration and clones reused noise buffers before caching them. This release targets standard GTNH biome support; heavily customized biome configurations need additional in-game verification.

## Coming from 2.8.x

This tool handles **terrain migration after upgrading the pack**, not the entire modpack upgrade. Download the official 2.9.0 server and client from [GTNH downloads](https://www.gtnewhorizons.com/downloads/) and follow [Installing and Migrating](https://wiki.gtnewhorizons.com/wiki/Installing_and_Migrating). First test the full upgraded world. Resolve registry prompts and pack-specific changes there; the wizard does not auto-confirm missing blocks or migrate old crops.

## Roll back

Stop the trial server and start the original server. If adopting the trial involved changing a system service, restore that service's original paths too. Progress made in the two copies is separate. The complete world archive in `.migration` provides an additional recovery copy; extract it to a **new** location with the matching server version.

Do not connect an old 2.8.x client to a 2.9.0 server. The optional client source must already match your server's pack version; the wizard changes RWG2 settings and map identity, not mod versions.

## Troubleshooting

- **No claims?** Claim your bases with Server Utilities first, or add a matching Prism client and select waypoints. Other claim systems are not supported in this release.
- **World changed?** Stop the server, read it again, and recalculate. Let players log out in preserved areas first. Their saved positions are shown if they fall outside the selection; the tool does not teleport them.
- **No matching waypoints?** The client must have visited this server using its JourneyMap World ID. Other servers' map folders are left alone.
- **Preview build failed?** Check JDK 21 and internet access. The wizard gives the local build log path. Downloads go to official upstream build repositories, not through a bundled proxy.
- **Restricted network?** `GTNH_GRADLE_ARGS` can supply Gradle JVM options, for example `-Dhttps.proxyHost=HOST -Dhttps.proxyPort=PORT`. `GTNH_MIGRATOR_CACHE` changes the cache location. Do not put credentials in an issue report.
- **Not enough space?** Allow room for a full server copy, an additional complete world archive, and the optional client copy. Very large selections can make search slower; at most 1,000 boundary columns are sampled.
- **Address already in use?** Run `python3 -m gtnh_migrator --port 0` to choose a free local port. `--no-browser` prints the URL without opening it.

## Development and verification

```sh
python3 -m unittest discover -v
```

Tests use generated synthetic worlds. They cover raw chunk retention, negative coordinates, NBT payload preservation, complete-copy verification, backup creation, other-dimension/client-cache preservation, changing-source rejection, and local API access checks. CI runs on Linux, macOS, and Windows with Python 3.11 and 3.13. Java preview validation requires the upstream dependencies and is a separate integration check.

The UI binds only to `127.0.0.1`, validates Host/Origin, and requires a per-session token for local filesystem API requests. There are no accounts, analytics, world uploads, or remote reporting. Only the generator's source and build dependencies are downloaded. Never expose the wizard through a public tunnel.

## License and credits

GPL-3.0-or-later; see [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md). Independent community project, not an official GTNH tool. Minecraft, GTNH, mods, and world data are not redistributed. This is an early **0.1 beta**: keep the original world and review the copy in game.
