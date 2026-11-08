"""Read-only inspection, reproducible plans, and verified migration into new folders."""
import gzip
import hashlib
import json
import re
import shutil
import tarfile
import uuid
from collections import defaultdict
from pathlib import Path
from . import nbt, region

OFFSET_KEYS = ['Biome Placement Offset X', 'Biome Placement Offset Z',
               'Landmass Placement Offset X', 'Landmass Placement Offset Z']


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def manifest(root):
    result = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_symlink():
            raise ValueError("Symbolic links are not supported: " + str(path))
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
        elif not path.is_dir():
            raise ValueError("Special filesystem entry is not supported")
    return result


def properties(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines()
                if '=' in line and not line.lstrip().startswith(('#', '!')))


def components(points):
    remaining, groups = set(points), []
    while remaining:
        stack = [min(remaining)]
        remaining.remove(stack[0])
        found = set(stack)
        while stack:
            x, z = stack.pop()
            for other in [(x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)]:
                if other in remaining:
                    remaining.remove(other)
                    found.add(other)
                    stack.append(other)
        groups.append(found)
    return sorted(groups, key=lambda group: (-len(group), min(group)))


def bounds(points):
    return [min(x for x, z in points), min(z for x, z in points),
            max(x for x, z in points), max(z for x, z in points)]


def expand(points, padding):
    result = set()
    for x, z in points:
        for dx in range(-padding, padding + 1):
            for dz in range(-padding, padding + 1):
                result.add((x + dx, z + dz))
                if len(result) > 1000000:
                    raise ValueError("Preservation area exceeds one million chunks")
    return result


def locate(server):
    root = Path(server).expanduser().resolve()
    if not (root / 'server.properties').is_file():
        raise ValueError("Choose a GTNH server folder containing server.properties")
    name = properties(root / 'server.properties').get('level-name', 'world')
    world = (root / name).resolve()
    if not world.is_relative_to(root) or world == root or '\\' in name:
        raise ValueError("Unsupported world path in server.properties")
    if not (world / 'level.dat').is_file():
        raise ValueError("World level.dat was not found")
    return root, world


def inspect(server, client=''):
    root, world = locate(server)
    if not (root / 'mods/rwg2-2.0.6.jar').is_file() or not (root / 'config/rwg2.cfg').is_file():
        raise ValueError("RWG2 2.0.6 is required. First prepare and test a GTNH 2.9.0 server copy using the official migration guide.")
    if not (root / 'lwjgl3ify-forgePatches.jar').is_file() or not (root / 'java9args.txt').is_file():
        raise ValueError("This release supports the GTNH Java 17–26 server distribution")
    level = nbt.loads((world / 'level.dat').read_bytes())['Data']
    if level['generatorName'] not in ('RWG', 'RWG2', 'RWG2_CONTINENTS'):
        raise ValueError("Unsupported source generator: " + level['generatorName'])
    teams = defaultdict(set)
    dimensions = defaultdict(int)
    for path in sorted((world / 'serverutilities/teams/claimedchunks').glob('*.dat')):
        data = nbt.loads(path.read_bytes()).get('ClaimedChunks', {})
        for dim, claims in data.items():
            dimensions[str(dim)] += len(claims)
            if str(dim) == '0':
                teams[path.stem].update((int(c['x']), int(c['z'])) for c in claims)
    groups = []
    for team, points in teams.items():
        for i, points in enumerate(components(points)):
            groups.append({'id': f'{team}:{i}', 'team': team, 'count': len(points),
                           'chunks': sorted(points), 'bounds': bounds(points)})
    groups.sort(key=lambda group: (-group['count'], group['id']))
    journey = root / 'config/JourneyMapServer' / (world.name + '.cfg')
    world_id = json.loads(journey.read_text()).get('WorldID') if journey.exists() else None
    waypoints, map_folders = [], []
    client_root = None
    if client:
        client_root = Path(client).expanduser().resolve()
        if client_root.name == '.minecraft' and (client_root.parent / 'instance.cfg').is_file():
            client_root = client_root.parent
        if not (client_root / 'instance.cfg').is_file():
            raise ValueError("Client copying currently supports Prism/MultiMC instances. Select the instance folder containing instance.cfg, or omit the client and sync rwg2.cfg manually.")
        mc = client_root / '.minecraft' if (client_root / '.minecraft').is_dir() else client_root
        if not (mc / 'mods').is_dir():
            raise ValueError("Choose a Prism instance folder or its .minecraft folder")
        if world_id:
            map_folders = sorted((mc / 'journeymap/data/mp').glob('*' + world_id.replace('-', '~') + '*'))
        for folder in map_folders:
            for path in sorted((folder / 'waypoints').glob('*.json')):
                data = json.loads(path.read_text())
                if 0 in data.get('dimensions', []):
                    waypoints.append({'id': str(path.relative_to(mc)), 'name': data['name'],
                                      'x': int(data['x']), 'z': int(data['z'])})
    players = []
    for path in sorted((world / 'playerdata').glob('*.dat')):
        player = nbt.loads(path.read_bytes())
        players.append({'id': path.stem, 'dimension': player.get('Dimension'), 'position': player.get('Pos')})
    region_files = list((world / 'region').glob('r.*.*.mca'))
    size = sum(path.stat().st_size for path in world.rglob('*') if path.is_file())
    return {'server': str(root), 'world': str(world), 'world_name': world.name,
            'client': str(client_root) if client_root else '', 'seed': level['RandomSeed'],
            'generator': level['generatorName'], 'groups': groups, 'waypoints': waypoints,
            'journeymap_world_id': world_id, 'mapped_client_folders': len(map_folders),
            'claims_by_dimension': dict(dimensions), 'players': players,
            'region_files': len(region_files), 'world_bytes': size,
            'world_revision': revision(world)}


def revision(world):
    # Fast invalidation during planning. Full SHA-256 verification runs during copying.
    h = hashlib.sha256()
    for path in sorted(Path(world).rglob('*')):
        if path.is_file():
            stat = path.stat()
            h.update(f'{path.relative_to(world)}\0{stat.st_size}\0{stat.st_mtime_ns}\n'.encode())
    return h.hexdigest()


def build_plan(info, selection):
    world = Path(info['world'])
    if revision(world) != info['world_revision']:
        raise ValueError("The world changed. Stop the server and inspect it again.")
    padding = int(selection.get('padding', 1))
    if not 0 <= padding <= 32:
        raise ValueError("Padding must be between 0 and 32 chunks")
    selected = set(selection.get('groups', []))
    selected_waypoints = set(selection.get('waypoints', []))
    groups = [g for g in info['groups'] if g['id'] in selected]
    if selected != {g['id'] for g in groups}:
        raise ValueError("Unknown claim area")
    keep = expand({tuple(c) for g in groups for c in g['chunks']}, padding)
    for wp in info['waypoints']:
        if wp['id'] in selected_waypoints:
            keep.update(expand({(wp['x'] // 16, wp['z'] // 16)}, padding))
    if not keep:
        raise ValueError("Select at least one claimed area or waypoint")
    if len(keep) > 1000000:
        raise ValueError("Preservation area exceeds one million chunks")
    chunks = {}
    existing_count = 0
    boundary = []
    for x, z in sorted(keep):
        for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            if (x + dx, z + dz) in keep:
                continue
            for v in range(0, 16, 4):
                ix = x * 16 + (0 if dx < 0 else 15) if dx else x * 16 + v
                iz = z * 16 + (0 if dz < 0 else 15) if dz else z * 16 + v
                boundary.append((ix, iz, ix + dx, iz + dz))
    if len(boundary) > 1000:
        boundary = [boundary[i * len(boundary) // 1000] for i in range(1000)]
    wanted = {(ix // 16, iz // 16) for ix, iz, x, z in boundary}
    retained = 0
    for path in sorted((world / 'region').glob('r.*.*.mca')):
        for chunk in region.read(path):
            existing_count += 1
            key = (chunk.x, chunk.z)
            if key in keep:
                retained += 1
            if key in wanted:
                chunks[key] = chunk.decode()
    if not retained:
        raise ValueError("None of the selected chunks exist in this world")
    survey = []
    skipped = 0
    for ix, iz, x, z in boundary:
        data = chunks.get((ix // 16, iz // 16))
        if data is None:
            skipped += 1
            continue
        try:
            survey.append([x, z, region.ground(data, ix % 16, iz % 16)])
        except ValueError:
            skipped += 1
    if not survey:
        raise ValueError("No usable boundary terrain samples; enlarge the selected area")
    targets = []
    for group in groups:
        biome = str(selection.get('biomes', {}).get(group['id'], '')).strip()
        if not biome:
            continue
        if len(biome) > 100 or any(char in biome for char in '\t\r\n|'):
            raise ValueError("Enter a single biome name")
        x0, z0, x1, z1 = bounds(expand({tuple(c) for c in group['chunks']}, padding))
        x0, z0, x1, z1 = x0 * 16 - 32, z0 * 16 - 32, (x1 + 1) * 16 + 32, (z1 + 1) * 16 + 32
        for i in range(9):
            x, z = round(x0 + (x1 - x0) * i / 8), round(z0 + (z1 - z0) * i / 8)
            for px, pz in {(x, z0), (x, z1), (x0, z), (x1, z)}:
                if (px // 16, pz // 16) not in keep:
                    targets.append([px, pz, biome])
    outside_players = [p for p in info['players'] if p['dimension'] == 0 and p['position']
                       and (int(p['position'][0] // 16), int(p['position'][2] // 16)) not in keep]
    if revision(world) != info['world_revision']:
        raise ValueError("The world changed while preparing the plan")
    return {'info': info, 'selection': selection, 'keep': sorted(keep), 'survey': survey,
            'targets': sorted(targets), 'existing_chunks': existing_count, 'retained_chunks': retained,
            'regenerate_chunks': existing_count - retained, 'skipped_samples': skipped,
            'outside_players': outside_players, 'candidate': None}


def patch_offsets(data, offsets):
    for key, value in zip(OFFSET_KEYS, offsets, strict=True):
        if not -30000000 <= int(value) <= 30000000:
            raise ValueError("RWG2 offset out of range")
        data, count = re.subn(r'(?m)^(\s*I:"' + re.escape(key) + r'"=)-?\d+\s*$',
                              lambda match: match[1] + str(int(value)), data)
        if count != 1:
            raise ValueError("Missing or duplicate RWG2 setting: " + key)
    return data


def new_target(target, source):
    target = Path(target).expanduser().resolve()
    source = Path(source).resolve()
    if target.exists() or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("Choose a new folder outside the original folder")
    if not target.parent.is_dir():
        raise ValueError("The parent folder must already exist")
    return target


def clone_client(source, target, old_id, new_id, cfg, keep):
    source = Path(source)
    target = new_target(target, source)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('natives', 'logs', 'crash-reports', 'backups', '.DS_Store'))
    mc = target / '.minecraft' if (target / '.minecraft').is_dir() else target
    (mc / 'config/rwg2.cfg').write_text(cfg)
    if (target / 'instance.cfg').exists():
        p = target / 'instance.cfg'
        p.write_text(re.sub(r'(?m)^name=.*$', 'name=' + target.name, p.read_text()))
    archive = target / '.migration/old-overworld-cache'
    if old_id:
        for folder in list((mc / 'journeymap/data/mp').glob('*' + old_id.replace('-', '~') + '*')):
            renamed = folder.with_name(folder.name.replace(old_id.replace('-', '~'), new_id.replace('-', '~')))
            folder.rename(renamed)
            if (renamed / 'DIM0').is_dir():
                dst = archive / 'journeymap' / renamed.name / 'DIM0'
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(renamed / 'DIM0', dst)
    # VP world ID is unrelated to JourneyMap. Select the correct world using the caller's world name.
    return target, mc, archive


def apply(plan, target, client_target='', progress=lambda message: None):
    info = plan['info']
    source, world = locate(info['server'])
    if not plan.get('candidate'):
        raise ValueError("Choose a calculated generation candidate first")
    if revision(world) != info['world_revision']:
        raise ValueError("The source world changed. Inspect and calculate again with the server stopped.")
    target = new_target(target, source)
    if client_target and not info['client']:
        raise ValueError("No source client was selected")
    if info['client'] and not client_target:
        raise ValueError("Choose a new client folder, or remove the source client from the plan")
    client_path = new_target(client_target, info['client']) if client_target else None
    origins = [source] + ([Path(info['client']).resolve()] if info['client'] else [])
    for destination in [target] + ([client_path] if client_path else []):
        if any(destination.is_relative_to(origin) or origin.is_relative_to(destination) for origin in origins):
            raise ValueError("Destination folders must be outside both original server and client folders")
    if client_path and (client_path.is_relative_to(target) or target.is_relative_to(client_path)):
        raise ValueError("Client and server destinations must be separate folders")
    progress('Hashing the original world')
    original = manifest(world)
    required = sum(p.stat().st_size for p in source.rglob('*') if p.is_file()) + info['world_bytes']
    if client_path:
        client_bytes = sum(p.stat().st_size for p in Path(info['client']).rglob('*') if p.is_file())
        if client_path.parent.stat().st_dev == target.parent.stat().st_dev:
            required += client_bytes
        elif shutil.disk_usage(client_path.parent).free < client_bytes:
            raise ValueError("Not enough free space for the client copy")
    if shutil.disk_usage(target.parent).free < required:
        raise ValueError("Not enough free space for the server copy and a complete world backup")
    stage = target.with_name(target.name + '.partial-' + uuid.uuid4().hex[:8])
    progress('Copying the server into a new folder')
    shutil.copytree(source, stage, ignore=lambda folder, names: [n for n in names if
                    n == '.DS_Store' or (Path(folder) == source and n in ('logs', 'backups'))])
    trial = stage / world.relative_to(source)
    if manifest(trial) != original or manifest(world) != original:
        raise ValueError("The world changed while copying. The incomplete copy is in " + str(stage))
    work = stage / '.migration'
    work.mkdir(exist_ok=True)
    progress('Creating and verifying a complete world backup')
    backup = work / 'world-before-rwg2.tar.gz'
    with tarfile.open(backup, 'w:gz', compresslevel=1) as tar:
        tar.add(trial, arcname=trial.name, recursive=True)
    verified = {}
    with tarfile.open(backup, 'r:gz') as tar:
        for item in tar:
            if item.isfile():
                stream = tar.extractfile(item)
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
                verified[Path(item.name).relative_to(trial.name).as_posix()] = h.hexdigest()
    if verified != original:
        raise ValueError("Backup verification failed")
    keep = {tuple(c) for c in plan['keep']}
    progress('Preserving selected chunks and verifying their compressed records')
    retained = 0
    for path in sorted((trial / 'region').glob('r.*.*.mca')):
        selected = [c for c in region.read(path) if (c.x, c.z) in keep]
        retained += len(selected)
        if selected:
            region.write(path, selected)
        else:
            path.unlink()
    if retained != plan['retained_chunks']:
        raise ValueError("Retained chunk count changed")
    for name in ['level.dat', 'level.dat_old']:
        if (trial / name).exists():
            (trial / name).write_bytes(nbt.rwg2_level((trial / name).read_bytes()))
    offsets = plan['candidate']['offsets']
    cfg = patch_offsets((stage / 'config/rwg2.cfg').read_text(), offsets)
    (stage / 'config/rwg2.cfg').write_text(cfg)
    props = stage / 'server.properties'
    text = props.read_text()
    if re.search(r'(?m)^level-type=', text):
        text = re.sub(r'(?m)^level-type=.*$', 'level-type=RWG2_CONTINENTS', text)
    else:
        text += '\nlevel-type=RWG2_CONTINENTS\n'
    props.write_text(text)
    new_id = str(uuid.uuid4())
    journey = stage / 'config/JourneyMapServer' / (world.name + '.cfg')
    if journey.exists():
        data = json.loads(journey.read_text())
        data.update(WorldID=new_id, UseWorldID=True)
        journey.write_text(json.dumps(data, indent=2) + '\n')
    for cache in (stage / 'visualprospecting/server').glob(world.name + '_*/DIM0.dat'):
        dst = work / 'old-visualprospecting' / cache.parent.name / 'DIM0.dat'
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(cache, dst)
    vp = stage / 'config/visualprospecting.cfg'
    if vp.exists():
        vp.write_text(vp.read_text().replace('B:recacheVeins=false', 'B:recacheVeins=true'))
    progress('Verifying other dimensions, player data, claims, and quests')
    after = manifest(trial)
    changed = {'level.dat', 'level.dat_old'}
    expected_other = {k: v for k, v in original.items() if not k.startswith('region/') and k not in changed}
    if expected_other != {k: v for k, v in after.items() if not k.startswith('region/') and k not in changed}:
        raise ValueError("World data outside the overworld regions did not match")
    if manifest(world) != original:
        raise ValueError("Original world changed during migration")
    client_result = ''
    if client_path:
        progress('Creating a separate client and refreshing only its overworld maps')
        client_stage = client_path.with_name(client_path.name + '.partial-' + uuid.uuid4().hex[:8])
        cp, mc, archive = clone_client(info['client'], client_stage, info['journeymap_world_id'], new_id, cfg, keep)
        for cache in (mc / 'visualprospecting/client').glob('*/' + world.name + '_*/DIM0.dat'):
            dst = archive / 'visualprospecting' / cache.relative_to(mc / 'visualprospecting/client')
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(cache, dst)
        if (cp / 'instance.cfg').exists():
            f = cp / 'instance.cfg'
            f.write_text(re.sub(r'(?m)^name=.*$', 'name=' + client_path.name, f.read_text()))
        cp.rename(client_path)
        client_result = str(client_path)
    sh = '#!/bin/sh\nset -eu\ncd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nexec java -Xms${GTNH_MIN_RAM:-4G} -Xmx${GTNH_MAX_RAM:-6G} @java9args.txt -jar lwjgl3ify-forgePatches.jar nogui\n'
    (stage / 'start-rwg2-trial.sh').write_text(sh)
    (stage / 'start-rwg2-trial.sh').chmod(0o755)
    (stage / 'start-rwg2-trial.bat').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\njava -Xms4G -Xmx6G @java9args.txt -jar lwjgl3ify-forgePatches.jar nogui\r\npause\r\n')
    result = {'server': str(target), 'client': client_result, 'source_server': str(source),
              'backup': str(target / '.migration/world-before-rwg2.tar.gz'),
              'backup_sha256': digest(backup), 'retained_chunks': retained,
              'regenerate_chunks': plan['regenerate_chunks'], 'offsets': offsets,
              'unchanged_other_world_files': len(expected_other), 'source_world_unchanged': True,
              'generator': 'RWG2_CONTINENTS', 'journeymap_world_id': new_id,
              'candidate': plan['candidate'], 'outside_players': plan['outside_players']}
    (work / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (work / 'source-world-sha256.json').write_text(json.dumps(original, indent=2) + '\n')
    stage.rename(target)
    progress('Verified copy is ready')
    return result
