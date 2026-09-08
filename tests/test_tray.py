import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from g13_config import Config, properties, validate_binding
from g13_providers import render, api_usage, steam, codex_local

class ConfigTests(unittest.TestCase):
    def test_stats_timing_validation_and_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            c = Config(d)
            self.assertEqual(c.data['stats_poll_seconds'], 1)
            self.assertEqual(c.data['stats_average_seconds'], 5)
            c.data.update(stats_poll_seconds=2, stats_average_seconds=10)
            c.save([{} for _ in range(4)])
            for i in range(4):
                saved = properties(c.bindings / f'bindings-{i}.properties')
                self.assertEqual(saved['stats_poll_seconds'], '2')
                self.assertEqual(saved['stats_average_seconds'], '10')
            self.assertEqual(Config(d).data['stats_average_seconds'], 10)
            original = (c.bindings / 'bindings-0.properties').read_bytes()
            for poll, window in [(0,5),(2,1),(1,61),(True,5)]:
                c.data.update(stats_poll_seconds=poll, stats_average_seconds=window)
                with self.assertRaises(ValueError): c.save([{} for _ in range(4)])
                self.assertEqual((c.bindings / 'bindings-0.properties').read_bytes(), original)

    def test_preserve_and_backup_and_numbering(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'.g13/bindings-0.properties'
            p.parent.mkdir()
            original = '# keep comment\nG0=p,k.16\nstick_mode=keys\nlcd_logiframe_page2_cmd=echo existing\n'
            p.write_text(original)
            c = Config(d)
            maps = [{'G0':'p,k.30'} for _ in range(4)]
            backup = c.save(maps)
            self.assertEqual((backup/p.name).read_text(), original)
            loaded = properties(p)
            self.assertEqual(loaded['G0'], 'p,k.30')
            self.assertEqual(loaded['stick_mode'], 'keys')
            self.assertEqual(loaded['lcd_logiframe_page1_cmd'], '')
            self.assertEqual(loaded['mode_profiles'], '1')
            self.assertIn('# keep comment', p.read_text())
            self.assertEqual(properties(p.parent/'bindings-1.properties')['lcd_logiframe_page2_cmd'], 'echo existing')
            self.assertEqual(c.path.stat().st_mode & 0o777, 0o600)
            p.write_text(p.read_text()+'G9=p,k.4\n')
            with self.assertRaisesRegex(ValueError, 'outside'): c.save(maps)

    def test_validation_precedes_changes(self):
        with tempfile.TemporaryDirectory() as d:
            c = Config(d)
            with self.assertRaises(ValueError): c.save([{'G0':'p,k.999'}]*4)
            self.assertFalse(c.path.exists())
            with self.assertRaises(ValueError): c.save([{'G0':'m,999,1'}]*4)
            for value in ['p,k.0', 'p,k.300', 'p,k.3\ncolor=0,0,0', 'shell,rm']:
                with self.assertRaises(ValueError): validate_binding(value)

class ProviderTests(unittest.TestCase):
    def test_missing_credentials_no_network(self):
        with patch('g13_providers.os.environ', {}), patch('g13_providers.request') as req:
            self.assertIn('Configure connection', render({'source':'Steam'}, {}))
            req.assert_not_called()

    def test_secret_not_in_http_errors(self):
        with patch('g13_providers.request', side_effect=HTTPError('secret-key',403,'secret-key',{},None)):
            result = render({'source':'Discord'}, {'DISCORD_BOT_TOKEN':'secret-key','DISCORD_GUILD_ID':'123'})
        self.assertIn('403',result)
        self.assertNotIn('secret-key',result)

    def test_usage_pagination_and_cache(self):
        pages = [{'data':[{'results':[{'input_tokens':100,'output_tokens':5}]}], 'has_more':True, 'next_page':'two'}, {'data':[{'results':[{'input_tokens':20,'output_tokens':2}]}], 'has_more':False}]
        with patch('g13_providers.request', side_effect=pages):
            lines = api_usage({'OPENAI_ADMIN_KEY':'test'})
        self.assertIn('Input: 120',lines)
        self.assertIn('Output: 7',lines)
        with patch('g13_providers.request', return_value={'data':[{'results':[{'uncached_input_tokens':10,'cache_read_input_tokens':20,'cache_creation':{'ephemeral_5m_input_tokens':30,'ephemeral_1h_input_tokens':40},'output_tokens':5}]}]}):
            self.assertIn('Input: 100',api_usage({'ANTHROPIC_ADMIN_KEY':'test'},True))

    def test_display_bounds(self):
        output = render({'source':'Custom text','text':('x'*80+'\n')*10},{})
        self.assertEqual(len(output.splitlines()),5)
        self.assertTrue(all(len(line)<=26 for line in output.splitlines()))

    def test_codex_latest_counter_not_sum(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'sessions/test.jsonl';p.parent.mkdir()
            p.write_text('\n'.join(json.dumps({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':v,'output_tokens':2}}}}) for v in [10,20]))
            with patch.dict('g13_providers.os.environ', {'CODEX_HOME':d}):
                self.assertIn('Input: 20', codex_local())


class ProfileImportTests(unittest.TestCase):
    def test_symbolic_json_and_chords(self):
        from g13_profiles import convert_profile
        p={'id':9,'source_id':1,'format':'json','bindings':[
            {'key_label':'G1','action_type':'key','action_value':'1'},
            {'key_label':'G2','action_type':'key','action_value':'COMBO:LEFTCTRL+S'},
            {'key_label':'G3','action_type':'key','action_value':'TYPE:hello'},
            {'key_label':'M1','action_type':'key','action_value':'F1'}]}
        mapping,macros,warnings=convert_profile(p,{'macros':[]})
        self.assertEqual(mapping['G0'],'p,k.2')
        self.assertEqual(macros[mapping['G1']]['sequence'],'kd.29,kd.31,d.20,ku.31,ku.29')
        self.assertNotIn('G2',mapping)
        self.assertEqual(len(warnings),2)

    def test_target_preserves_other_modes_and_screen(self):
        with tempfile.TemporaryDirectory() as d:
            c=Config(d);c.save([{'G0':'p,k.16','G1':'p,k.17'}]*4)
            untouched=(c.bindings/'bindings-0.properties').read_bytes()
            before=properties(c.bindings/'bindings-2.properties')
            c.data['screens'][2]['color']='1,2,3' # unrelated unsaved UI edit
            backup,mapping=c.save_target(2,{'G0':'import:test'},{'import:test':{'name':'Save','sequence':'kd.29,kd.31,ku.31,ku.29'}})
            after=properties(c.bindings/'bindings-2.properties')
            self.assertEqual((c.bindings/'bindings-0.properties').read_bytes(),untouched)
            self.assertEqual(after['G1'],before['G1'])
            self.assertEqual(after['lcd_logiframe_page3_color'],before['lcd_logiframe_page3_color'])
            self.assertTrue(after['G0'].startswith('m,1000,'))
            self.assertTrue((backup/'bindings-2.properties').exists())
            with self.assertRaises(ValueError): c.save_target(2,{'G29':'p,k.1'})

    def test_credentials_do_not_save_pending_screens(self):
        with tempfile.TemporaryDirectory() as d:
            c=Config(d);c.save([{'G0':'p,k.16'}]*4)
            c.data['screens'][0]['color']='1,2,3'
            c.save_credentials({'OPENAI_ADMIN_KEY':'test'})
            saved=json.loads(c.path.read_text())
            self.assertNotEqual(saved['screens'][0]['color'],'1,2,3')
            self.assertEqual(saved['credentials']['OPENAI_ADMIN_KEY'],'test')
            self.assertEqual(c.path.stat().st_mode & 0o777,0o600)
            c.save_credentials({'OPENAI_ADMIN_KEY':''})
            self.assertEqual(json.loads(c.path.read_text())['credentials']['OPENAI_ADMIN_KEY'],'')

if __name__ == '__main__': unittest.main()
