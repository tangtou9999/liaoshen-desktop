import os
import tempfile
import unittest
from pathlib import Path
from liaoshen.config import crypt,Config,DEFAULTS

@unittest.skipUnless(os.name=='nt','未测试：Windows DPAPI 需要 Windows 真机或 Windows runner')
class WindowsConfigTests(unittest.TestCase):
    def test_encrypt_roundtrip(self):
        data='测试密钥-secret'.encode()
        encrypted=crypt(data)
        self.assertNotIn(data,encrypted)
        self.assertEqual(crypt(encrypted,True),data)
    def test_save_load(self):
        with tempfile.TemporaryDirectory() as folder:
            c=Config()
            c.path=Path(folder)/'settings.dpapi'
            settings=DEFAULTS | dict(key='test-only')
            c.save(settings)
            self.assertNotIn(b'test-only',c.path.read_bytes())
            self.assertEqual(c.load(),settings)
