import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from import_game_profiles import import_collection
from g13_profiles import convert_profile

class GameImportTests(unittest.TestCase):
    def test_modes_modifiers_macros_and_unsupported(self):
        xml='''<profiles xmlns="urn:profiles"><profile name="Test game"><macros>
        <macro guid="one" name="Move"><keystroke><key value="W"/></keystroke></macro>
        <macro guid="two" name="Save"><keystroke><modifier value="LCTRL"/><key value="S"/></keystroke></macro>
        <macro guid="three" name="Click"><mousefunction><do task="leftclick"/></mousefunction></macro>
        </macros><assignments devicecategory="Logitech.Gaming.LeftHandedController">
        <assignment contextid="G1" macroguid="one" shiftstate="1"/>
        <assignment contextid="G2" macroguid="two" shiftstate="1"/>
        <assignment contextid="G3" macroguid="three" shiftstate="1"/>
        <assignment contextid="G1" macroguid="two" shiftstate="2"/>
        <assignment contextid="G1" macroguid="three" shiftstate="1" backup="true"/>
        </assignments></profile></profiles>'''
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'game.xml').write_text(xml)
            data=import_collection(Path(d))
        self.assertEqual(len(data['profiles']),2)
        mapping,macros,warnings=convert_profile(data['profiles'][0],data)
        self.assertEqual(mapping['G0'],'p,k.17')
        self.assertIn('kd.29',macros[mapping['G1']]['sequence'])
        self.assertNotIn('G2',mapping)
        self.assertIn('mousefunction',warnings[0])

    def test_game_without_g13_assignments_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'empty.xml').write_text('<profiles><profile name="Empty game"/></profiles>')
            data=import_collection(Path(d))
        self.assertEqual(data['profiles'][0]['name'],'Empty game')
        self.assertTrue(data['profiles'][0]['notes'])

    def test_xml_auxiliary_controls_translate_to_driver_inputs(self):
        labels=['G23','G24','G25','G26','G27','G28','G29']
        xml='<profiles><profile name="Auxiliary test"><macros><macro guid="dot" name="Period"><keystroke><key value="PERIOD"/></keystroke></macro></macros><assignments devicecategory="Logitech.Gaming.LeftHandedController">'
        xml+=''.join(f'<assignment contextid="{label}" macroguid="dot" shiftstate="1"/>' for label in labels)
        xml+='</assignments></profile></profiles>'
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'aux.xml').write_text(xml)
            data=import_collection(Path(d))
        converted,_,warnings=convert_profile(data['profiles'][0],data)
        self.assertEqual(converted, {key:'p,k.52' for key in ['G33','G34','G36','G38','G39','G37']})
        self.assertEqual(len(warnings),1)
        self.assertIn('TOP',warnings[0])
        self.assertEqual([b['source_key_label'] for b in data['profiles'][0]['bindings']],labels)

if __name__=='__main__': unittest.main()
