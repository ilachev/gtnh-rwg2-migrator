"""Synthetic fixtures only: no player or production-world data."""
import gzip
import json
import struct
import zlib
from pathlib import Path
from gtnh_migrator.region import Chunk, write


def utf(value):
    raw = value.encode()
    return struct.pack('>H', len(raw)) + raw


def payload(typ, value):
    if typ in (1, 2, 3, 4, 5, 6):
        return struct.pack({1:'>b',2:'>h',3:'>i',4:'>q',5:'>f',6:'>d'}[typ], value)
    if typ == 8:
        return utf(value)
    if typ == 7:
        return struct.pack('>i', len(value)) + value
    if typ == 11:
        return struct.pack('>i', len(value)) + struct.pack('>' + 'i' * len(value), *value)
    if typ == 10:
        return b''.join(bytes([t]) + utf(name) + payload(t, v) for name, (t, v) in value.items()) + b'\0'
    if typ == 9:
        sub, entries = value
        return bytes([sub]) + struct.pack('>i', len(entries)) + b''.join(payload(sub, v) for v in entries)
    raise ValueError(typ)


def nbt(value):
    return b'\x0a\0\0' + payload(10, value)


def create(parent):
    server = Path(parent) / 'example-server'
    world = server / 'world'
    world.mkdir(parents=True)
    (server / 'mods').mkdir()
    (server / 'mods/rwg2-2.0.6.jar').write_bytes(b'TEST FIXTURE: not a playable mod')
    (server / 'lwjgl3ify-forgePatches.jar').write_bytes(b'TEST FIXTURE')
    (server / 'java9args.txt').write_text('')
    (server / 'server.properties').write_text('level-name=world\nlevel-type=RWG\nrcon.password=synthetic-example-only\n')
    (server / 'config/JourneyMapServer').mkdir(parents=True)
    old_id = '00000000-0000-4000-8000-000000000000'
    (server / 'config/JourneyMapServer/world.cfg').write_text(json.dumps({'WorldID':old_id,'UseWorldID':True}))
    (server / 'config/rwg2.cfg').write_text('"Expert / Worldgen Migration" {\n' + ''.join(' I:"'+key+'"=0\n' for key in ['Biome Placement Offset X','Biome Placement Offset Z','Landmass Placement Offset X','Landmass Placement Offset Z']) + '}\n')
    level = {'Data':(10,{'generatorName':(8,'RWG'),'generatorVersion':(3,0),'generatorOptions':(8,''),
                        'RandomSeed':(4,123456789),'SpawnX':(3,-8),'SpawnY':(3,65),'SpawnZ':(3,8),
                        'unrelated':(7,b'\x00\xff\x80\x01')})}
    (world / 'level.dat').write_bytes(gzip.compress(nbt(level),mtime=0))
    (world / 'level.dat_old').write_bytes((world / 'level.dat').read_bytes())
    claims = world / 'serverutilities/teams/claimedchunks'
    claims.mkdir(parents=True)
    data = {'ClaimedChunks':(10,{'0':(9,(10,[{'x':(3,-1),'z':(3,0),'loaded':(1,1)},
                                           {'x':(3,7),'z':(3,-3),'loaded':(1,0)}])),
                                '7':(9,(10,[{'x':(3,0),'z':(3,0)}]))})}
    (claims / 'Explorers.dat').write_bytes(gzip.compress(nbt(data),mtime=0))
    (world / 'DIM-1/region').mkdir(parents=True)
    (world / 'DIM-1/region/fixture.bin').write_bytes(b'other dimension must remain byte-identical')
    (world / 'betterquesting').mkdir()
    (world / 'betterquesting/QuestProgress.json').write_text('{"synthetic": true}')
    (world / 'playerdata').mkdir()
    player = {'Dimension':(3,0),'Pos':(9,(6,[-8.,65.,8.])),
              'Inventory':(9,(10,[{'id':(2,1),'Count':(1,32),'Slot':(1,0)}])),'XpLevel':(3,12)}
    (world / 'playerdata/00000000-0000-4000-8000-000000000001.dat').write_bytes(gzip.compress(nbt(player),mtime=0))
    regions = {}
    for x in range(-4,11):
        for z in range(-7,5):
            blocks = bytes([1])*4096
            section = {'Y':(1,3),'Blocks':(7,blocks)}
            chunk_nbt = nbt({'Level':(10,{'xPos':(3,x),'zPos':(3,z),'Sections':(9,(10,[section])),
                         'HeightMap':(11,[64]*256),'Biomes16v2':(7,struct.pack('<256H',*([51]*256)))})})
            compressed = zlib.compress(chunk_nbt)
            record = struct.pack('>I',len(compressed)+1)+b'\x02'+compressed
            regions.setdefault((x//32,z//32),[]).append(Chunk(x,z,b'\0\0\0\1',record))
    (world / 'region').mkdir()
    for (x,z),chunks in regions.items():
        write(world / f'region/r.{x}.{z}.mca',chunks)
    client = Path(parent) / 'example-client'
    mc = client / '.minecraft'
    (mc / 'mods').mkdir(parents=True)
    (mc / 'config').mkdir()
    (mc / 'config/rwg2.cfg').write_text((server / 'config/rwg2.cfg').read_text())
    (client / 'instance.cfg').write_text('[General]\nname=Example client\nJoinServerOnLaunch=false\n')
    jm = mc / ('journeymap/data/mp/Example_' + old_id.replace('-', '~'))
    for dim in ['DIM0','DIM-1']:
        (jm / dim).mkdir(parents=True)
        (jm / dim / 'tile.fixture').write_bytes(('original ' + dim).encode())
    (jm / 'waypoints').mkdir()
    (jm / 'waypoints/Base.json').write_text(json.dumps({'name':'Base','x':-8,'z':8,'dimensions':[0]}))
    (jm / 'waypoints/Trip.json').write_text(json.dumps({'name':'Trip','x':144,'z':32,'dimensions':[0]}))
    vp = mc / 'visualprospecting/client/example/world_fixture'
    vp.mkdir(parents=True)
    for dim in ['DIM0','DIM-1']:
        (vp / (dim+'.dat')).write_bytes(dim.encode())
    return server, client
