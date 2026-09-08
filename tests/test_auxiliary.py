import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from g13_config import Config, properties
from g13_profiles import convert_profile

class AuxiliaryTests(unittest.TestCase):
    def test_save_auxiliary_and_activate_key_mode(self):
        with tempfile.TemporaryDirectory() as d:
            c=Config(d);c.save([{'G0':'p,k.16'}]*4)
            p=c.bindings/'bindings-1.properties'
            with p.open('a') as f:f.write('stick_mode=absolute\n')
            c=Config(d)
            before=(c.bindings/'bindings-0.properties').read_bytes()
            c.save_target(1,{'G33':'p,k.57','G34':'p,k.28','G36':'p,k.17'})
            saved=properties(p)
            self.assertEqual(saved['stick_mode'],'keys')
            self.assertEqual(saved['G34'],'p,k.28')
            self.assertEqual((c.bindings/'bindings-0.properties').read_bytes(),before)
            with self.assertRaises(ValueError):c.save_target(1,{'G32':'p,k.16'})

    def test_import_canonical_auxiliary_labels(self):
        p={'id':1,'source_id':1,'format':'properties','bindings':[
            {'key_label':label,'action_type':'key','action_value':'17'} for label in ['LEFT','DOWN','STICK_UP','STICK_LEFT','STICK_RIGHT','STICK_DOWN']]}
        mapping,_,warnings=convert_profile(p,{'macros':[]})
        self.assertEqual(set(mapping),{'G33','G34','G36','G37','G38','G39'})
        self.assertEqual(warnings,[])
