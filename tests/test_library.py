import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from g13_library import group_library, compare_profiles
from g13_config import Config, properties
import g13_config


def profile(ident,name,bindings,origin='game.xml'):
    return {'id':ident,'source_id':1,'name':name,'origin':origin,'format':'properties',
            'bindings':[{'key_label':key,'action_type':'key','action_value':str(value)} for key,value in bindings.items()]}

class LibraryTests(unittest.TestCase):
    def test_grouped_modes_and_exact_vs_partial(self):
        data={'sources':[{'id':1,'repo':'test/games'}],'macros':[], 'profiles':[
            profile(1,'Game · source M1',{'G1':17,'G2':18}),
            profile(2,'Game · source M2',{'G1':17,'G2':18}),
            profile(3,'Other',{'G1':17},'other.xml')]}
        groups=group_library(data)
        self.assertEqual(len(groups),2)
        a,b=groups[0]['modes']
        self.assertTrue(compare_profiles(a,b)['exact'])
        self.assertIn('Identical modes',groups[0]['badges'])
        r=compare_profiles(a,groups[1]['modes'][0])
        self.assertFalse(r['exact']);self.assertFalse(r['same_editable'])
        self.assertEqual((r['equal'],r['shared'],r['only_a']),(1,1,1))

    def test_unsupported_and_outside_keys_not_ignored_as_exact(self):
        data={'sources':[{'id':1,'repo':'test/games'}],'macros':[], 'profiles':[
            profile(1,'One',{'G1':17,'M1':20},'a'),
            profile(2,'Two',{'G1':17,'M1':21},'b')]}
        groups=group_library(data)
        r=compare_profiles(groups[0]['modes'][0],groups[1]['modes'][0])
        self.assertFalse(r['exact']);self.assertTrue(r['same_editable'])

class BatchSaveTests(unittest.TestCase):
    def test_batch_preflight_and_single_backup(self):
        with tempfile.TemporaryDirectory() as d:
            c=Config(d);c.save([{'G0':'p,k.16'}]*4)
            fourth=(c.bindings/'bindings-3.properties').read_bytes()
            backup,patches=c.save_targets([(i,{'G0':f'p,k.{20+i}'},{}) for i in range(3)])
            self.assertEqual(len(list(backup.glob('bindings-*'))),3)
            self.assertEqual((c.bindings/'bindings-3.properties').read_bytes(),fourth)
            before=(c.bindings/'bindings-0.properties').read_bytes()
            with self.assertRaises(ValueError):c.save_targets([(0,{'G0':'p,k.30'},{}),(1,{'G0':'invalid'}, {})])
            self.assertEqual((c.bindings/'bindings-0.properties').read_bytes(),before)
            with self.assertRaises(ValueError):c.save_targets([(0,{},{}),(0,{},{})])

    def test_write_failure_rolls_back_and_removes_new_macros(self):
        with tempfile.TemporaryDirectory() as d:
            c=Config(d);c.save([{'G0':'p,k.16'}]*4)
            before=[(c.bindings/f'bindings-{i}.properties').read_bytes() for i in range(4)]
            real=g13_config.update_properties
            def write(path,changes):
                if path.name=='bindings-1.properties':raise OSError('simulated full disk')
                return real(path,changes)
            imported={'import:a':{'name':'A','sequence':'kd.30,ku.30'}}
            with patch('g13_config.update_properties',side_effect=write):
                with self.assertRaises(OSError):c.save_targets([(0,{'G0':'import:a'},imported),(1,{'G0':'p,k.30'}, {})])
            self.assertEqual([(c.bindings/f'bindings-{i}.properties').read_bytes() for i in range(4)],before)
            self.assertEqual(list(c.bindings.glob('macro-*.properties')),[])

    def test_changed_later_target_prevents_earlier_write(self):
        with tempfile.TemporaryDirectory() as d:
            c=Config(d);c.save([{'G0':'p,k.16'}]*4)
            before=(c.bindings/'bindings-0.properties').read_bytes()
            (c.bindings/'bindings-2.properties').write_text('G0=p,k.3\n')
            with self.assertRaises(ValueError):c.save_targets([(0,{'G0':'p,k.20'},{}),(2,{'G0':'p,k.21'}, {})])
            self.assertEqual((c.bindings/'bindings-0.properties').read_bytes(),before)
