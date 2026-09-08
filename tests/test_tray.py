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

if __name__ == '__main__': unittest.main()
