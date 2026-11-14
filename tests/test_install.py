import datetime
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('installer', Path(__file__).parents[1] / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {'VERSION': '1.0.3', 'EXTRAS': '', 'RUNNER_TEMP': self.tmp.name}
        self.today = datetime.date(2026, 11, 14)

    def prepare(self, **changes):
        return installer.prepare(self.env | changes, self.today)

    def test_version_and_extras_change_cache(self):
        base = self.prepare()
        self.assertNotEqual(base['key'], self.prepare(VERSION='1.0.4')['key'])
        self.assertNotEqual(base['key'], self.prepare(EXTRAS='ai')['key'])
        self.assertEqual(self.prepare(EXTRAS='ai,other')['key'], self.prepare(EXTRAS='other,ai')['key'])

    def test_platform_python_and_week_change_cache(self):
        base = self.prepare()['key']
        for attr in ['system', 'machine', 'python_version', 'python_implementation']:
            with patch.object(installer.platform, attr, return_value='different'):
                self.assertNotEqual(base, self.prepare()['key'])
        self.assertNotEqual(base, installer.prepare(self.env, self.today + datetime.timedelta(days=7))['key'])

    def test_pin_and_explicit_precedence(self):
        pin = Path(self.tmp.name) / '.docassert-version'
        pin.write_text('1.0.2\n')
        self.assertEqual(self.prepare(VERSION='', VERSION_FILE=str(pin))['spec'], 'docassert==1.0.2')
        self.assertEqual(self.prepare(VERSION_FILE=str(pin))['spec'], 'docassert==1.0.3')

    def test_latest_is_resolved_each_run(self):
        env = self.env | {'VERSION': ''}
        a = installer.prepare(env, self.today, latest='1.0.3')
        b = installer.prepare(env, self.today, latest='1.0.4')
        self.assertNotEqual(a['key'], b['key'])
        self.assertEqual(b['spec'], 'docassert==1.0.4')

    def test_invalid_inputs(self):
        for value in ['--index-url=evil', '1.2.3\nkey=evil', '1.2.*', '1.2.3;echo bad']:
            with self.assertRaises(ValueError): self.prepare(VERSION=value)
        for value in ['ai] @ https://evil', 'ai\nkey=bad', '--foo']:
            with self.assertRaises(ValueError): self.prepare(EXTRAS=value)

    def test_cold_then_warm_never_uses_index(self):
        data = self.prepare()
        run = Mock(return_value=Mock(returncode=0))
        installer.install(data['spec'], data['directory'], run=run)
        self.assertEqual(run.call_args_list[0].args[0][3], 'wheel')
        run.reset_mock()
        installer.install(data['spec'], data['directory'], run=run)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn('--no-index', commands[0])
        self.assertNotIn('wheel', commands[0])
        self.assertEqual(commands[1], ['docassert', '--version'])

    def test_failed_preparation_retries_without_caching_partial(self):
        data = self.prepare()
        run = Mock(side_effect=[Mock(returncode=1)] * 4)
        sleep = Mock()
        with self.assertRaises(RuntimeError): installer.install(data['spec'], data['directory'], run=run, sleep=sleep)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(sleep.call_count, 3)
        self.assertFalse((Path(data['directory']) / '.complete').exists())

    def test_wrong_marker_rebuilds(self):
        data = self.prepare()
        folder = Path(data['directory']); folder.mkdir()
        (folder / '.complete').write_text('docassert==0.0.1')
        run = Mock(return_value=Mock(returncode=0))
        installer.install(data['spec'], data['directory'], run=run)
        self.assertEqual(run.call_args_list[0].args[0][3], 'wheel')

    def test_empty_pin_fails_instead_of_silently_tracking_latest(self):
        pin = Path(self.tmp.name) / '.docassert-version'
        pin.write_text('')
        with self.assertRaises(ValueError):
            self.prepare(VERSION='', VERSION_FILE=str(pin))

    def test_corrupt_complete_cache_fails_without_network_fallback(self):
        data = self.prepare()
        folder = Path(data['directory']); folder.mkdir()
        (folder / '.complete').write_text(data['spec'])
        run = Mock(side_effect=subprocess.CalledProcessError(1, ['pip']))
        with self.assertRaises(subprocess.CalledProcessError):
            installer.install(data['spec'], data['directory'], run=run)
        self.assertEqual(run.call_count, 1)
        self.assertIn('--no-index', run.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
