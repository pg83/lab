import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('cg_proton_test', Path(__file__).resolve().parents[1] / 'lab/cg.py')
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)


class ProtonServiceTests(unittest.TestCase):
    def test_key_is_passed_in_inherited_memfd(self):
        service = cg.ProtonStealth(8057, '/proton/stealth/nl-free-243', '185.185.50.91:443')
        config = b'test-only-config\n'
        descriptors = []

        class ExecCalled(Exception):
            pass

        def execute(*args, **kwargs):
            self.assertEqual(args[0], 'proton-stealth')
            path = args[args.index('-config') + 1]
            self.assertTrue(path.startswith('/proc/self/fd/'))
            fd = int(path.rsplit('/', 1)[-1])
            descriptors.append(fd)
            self.assertTrue(os.get_inheritable(fd))
            with open(path, 'rb') as stream:
                self.assertEqual(stream.read(), config)
            self.assertEqual(args[args.index('-socks') + 1], '127.0.0.1:8057')
            self.assertEqual(args[args.index('-endpoint') + 1], '185.185.50.91:443')
            self.assertEqual(kwargs, {'PATH': '/bin'})
            self.assertNotIn(config.decode().strip(), args)
            raise ExecCalled()

        with patch.object(cg, 'get_key', return_value=config) as key, patch.object(cg, 'exec_into', side_effect=execute):
            with self.assertRaises(ExecCalled):
                service.run()
        key.assert_called_once_with('/proton/stealth/nl-free-243')
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_service_is_independent_of_cloudflared(self):
        service = cg.ProtonStealth(8057, '/proton/stealth/nl-free-243', '185.185.50.91:443')
        self.assertEqual(service.name(), 'proton_stealth_nl')
        self.assertEqual(service.user(), 'root')
        self.assertEqual(list(service.pkgs()), [{'pkg': 'bin/proton/stealth'}])


if __name__ == '__main__':
    unittest.main()
