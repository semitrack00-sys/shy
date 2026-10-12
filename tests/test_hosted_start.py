import importlib.util
import os
from pathlib import Path
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch,Mock
P=Path(__file__).resolve().parents[1]/'scripts/hosted_start.py'
spec=importlib.util.spec_from_file_location('hosted_start',P);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ENV={'SHY_ACCESS_TOKEN':'t'*40,'SHY_OWNER_PASSWORD':'p'*8,'SHY_OWNER_USERNAME':'owner','SHY_PUBLIC_ORIGIN':'https://shy.example','DATABASE_URL':'fixture','PORT':'10000'}
class Startup(unittest.TestCase):
    def test_missing_secrets_and_conflicting_public_port_never_launch(self):
        for extra in [{'SHY_ACCESS_TOKEN':''},{'SHY_OWNER_PASSWORD':''},{'SHY_OWNER_PASSWORD':'p'*7},{'DATABASE_URL':''},{'PORT':'8000'}]:
            with patch.dict(os.environ,{**ENV,**extra}),patch.object(mod.subprocess,'Popen',side_effect=AssertionError('Do not launch')):
                with self.assertRaises(RuntimeError):mod.main()
    def test_failed_child_stops_partner_and_core_is_loopback_only(self):
        core=Mock();core.poll.return_value=None
        web=Mock();web.poll.return_value=1
        with patch.dict(os.environ,ENV),patch.object(mod.signal,'signal'),patch.object(mod.subprocess,'Popen',side_effect=[core,web]) as launch,patch.object(mod,'urlopen',return_value=nullcontext(SimpleNamespace(status=200))):
            self.assertEqual(mod.main(),1)
        core.terminate.assert_called_once();core.wait.assert_called_once();web.wait.assert_called_once()
        self.assertIn('127.0.0.1',launch.call_args_list[0].args[0]);self.assertIn('0.0.0.0',launch.call_args_list[1].args[0])
        self.assertEqual(launch.call_args_list[1].kwargs['env']['SHY_BACKEND_BASE_URL'],'http://127.0.0.1:8000')
if __name__=='__main__':unittest.main()
