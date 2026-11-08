import gzip
import json
import shutil
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from gtnh_migrator import nbt, region, world
from gtnh_migrator.app import State, handler
from .fixtures import create


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.server, self.client = create(self.base)

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, client=True):
        info = world.inspect(self.server, self.client if client else '')
        return world.build_plan(info, {'groups':[g['id'] for g in info['groups']],
                                      'waypoints':[], 'padding':1, 'biomes':{}})

    def test_copy_preserves_all_other_data_and_raw_chunk_records(self):
        before = world.manifest(self.server / 'world')
        source_records = {(c.x,c.z):(c.timestamp,c.record) for p in (self.server/'world/region').glob('*.mca') for c in region.read(p)}
        plan = self.plan()
        self.assertEqual(plan['retained_chunks'],18)
        plan['candidate']={'offsets':[640,-128,0,0],'max':5,'mean':1}
        result = world.apply(plan,self.base/'new-server',self.base/'new-client')
        self.assertEqual(world.manifest(self.server/'world'),before)
        target = Path(result['server'])/'world'
        self.assertEqual(nbt.loads((target/'level.dat').read_bytes())['Data']['generatorName'],'RWG2_CONTINENTS')
        actual = {(c.x,c.z):(c.timestamp,c.record) for p in (target/'region').glob('*.mca') for c in region.read(p)}
        self.assertEqual(actual,{k:v for k,v in source_records.items() if k in map(tuple,plan['keep'])})
        after = world.manifest(target)
        for name,sha in before.items():
            if not name.startswith('region/') and name not in ('level.dat','level.dat_old'):
                self.assertEqual(after[name],sha,name)
        new_client=Path(result['client'])
        self.assertIn('name=new-client',(new_client/'instance.cfg').read_text())
        jm=list((new_client/'.minecraft/journeymap/data/mp').iterdir())[0]
        self.assertFalse((jm/'DIM0').exists())
        self.assertEqual((jm/'DIM-1/tile.fixture').read_bytes(),b'original DIM-1')
        self.assertEqual((new_client/'.minecraft/visualprospecting/client/example/world_fixture/DIM-1.dat').read_bytes(),b'DIM-1')
        self.assertFalse((new_client/'.minecraft/visualprospecting/client/example/world_fixture/DIM0.dat').exists())
        self.assertTrue(Path(result['backup']).is_file())

    def test_existing_or_nested_destinations_are_refused(self):
        for path in [self.server,self.server/'child',self.base]:
            with self.assertRaises(ValueError):world.new_target(path,self.server)

    def test_changing_source_invalidates_plan(self):
        info=world.inspect(self.server)
        (self.server/'world/changed.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            world.build_plan(info,{'groups':[info['groups'][0]['id']]})

    def test_apply_rejects_changed_world(self):
        plan=self.plan(False);plan['candidate']={'offsets':[0,0,0,0]}
        (self.server/'world/changed.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            world.apply(plan,self.base/'new')
        self.assertFalse((self.base/'new').exists())

    def test_destinations_cannot_modify_the_other_original(self):
        plan=self.plan();plan['candidate']={'offsets':[0,0,0,0]}
        for server_dest,client_dest in [(self.client/'new-server',self.base/'new-client'),
                                        (self.base/'new-server',self.server/'new-client')]:
            with self.assertRaisesRegex(ValueError,'outside both'):
                world.apply(plan,server_dest,client_dest)

    def test_empty_selection_is_refused(self):
        info=world.inspect(self.server)
        with self.assertRaisesRegex(ValueError,'at least one'):
            world.build_plan(info,{'groups':[],'waypoints':[]})

    def test_negative_coordinates_and_waypoint_selection(self):
        info=world.inspect(self.server,self.client)
        plan=world.build_plan(info,{'groups':[info['groups'][0]['id']],'padding':0,'waypoints':[info['waypoints'][1]['id']]})
        self.assertIn((-1,0),plan['keep'])
        self.assertIn((9,2),plan['keep'])
        self.assertEqual(len(plan['keep']),2)

    def test_nbt_patch_changes_only_generator_payload_spans(self):
        raw=(self.server/'world/level.dat').read_bytes()
        old=nbt.unpack(raw);a=old.parse()
        updated=nbt.rwg2_level(raw);new=nbt.unpack(updated);b=new.parse()
        for key in ('generatorName','generatorVersion','generatorOptions'):
            a['Data'].pop(key);b['Data'].pop(key)
        self.assertEqual(a,b)
        def unrelated(reader):
            raw=reader.raw
            for start,end,_ in sorted(reader.spans.values(),reverse=True):raw=raw[:start]+raw[end:]
            return raw
        self.assertEqual(unrelated(old),unrelated(new))

    def test_region_detects_overlapping_sectors(self):
        path=next((self.server/'world/region').glob('*.mca'))
        raw=bytearray(path.read_bytes());slots=[i for i in range(1024) if raw[i*4:i*4+4]!=b'\0'*4]
        raw[slots[1]*4:slots[1]*4+4]=raw[slots[0]*4:slots[0]*4+4]
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'Overlapping'):region.read(path)

    def test_blocks16_ground_is_big_endian(self):
        blocks=bytearray(8192);struct.pack_into('>H',blocks,(15*256+3*16+2)*2,1)
        data={'Sections':[{'Y':3,'Blocks16':bytes(blocks)}],'HeightMap':[64]*256}
        self.assertEqual(region.ground(data,2,3),63)


class WebAccessTest(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(State(),'test-token'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def test_auth_and_host_protect_local_filesystem(self):
        for headers in [{},{'X-Migration-Token':'test-token','Host':'attacker.example'},
                        {'X-Migration-Token':'test-token','Origin':'https://attacker.example'}]:
            req=urllib.request.Request(self.url+'/api/state',headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
            self.assertEqual(err.exception.code,403)
            err.exception.close()
        req=urllib.request.Request(self.url+'/api/state',headers={'X-Migration-Token':'test-token'})
        with urllib.request.urlopen(req) as response:self.assertFalse(json.load(response)['job']['busy'])

    def test_static_ui_and_unknown_routes(self):
        with urllib.request.urlopen(self.url) as response:
            html=response.read();self.assertIn(b'Create verified copy',html);self.assertNotIn(b'__TOKEN__',html)
        with self.assertRaises(urllib.error.HTTPError) as err:urllib.request.urlopen(self.url+'/../server.properties')
        err.exception.close()


if __name__=='__main__':unittest.main()
