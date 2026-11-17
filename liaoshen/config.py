"""Windows per-user DPAPI encryption, including API key and persona."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from .core import AppError

DEFAULTS = dict(key='', persona='自然、真诚、有分寸', language='自动识别', opacity=95, size=64)

class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

def crypt(data, decrypt=False):
    if os.name != 'nt':
        raise AppError('加密配置仅支持 Windows 10/11（使用当前 Windows 用户的 DPAPI）。')
    buf = ctypes.create_string_buffer(data)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    out = Blob()
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    api.CryptProtectData.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    api.CryptProtectData.restype = wintypes.BOOL
    api.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    api.CryptUnprotectData.restype = wintypes.BOOL
    if decrypt:
        ok = api.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(out))
    else:
        ok = api.CryptProtectData(ctypes.byref(src), 'LiaoShen', None, None, None, 1, ctypes.byref(out))
    if not ok:
        raise AppError('配置加密或解密失败。请使用原 Windows 账户，或备份后删除配置重新填写。')
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel = ctypes.WinDLL('kernel32')
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))

class Config:
    def __init__(self):
        self.path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'LiaoShenDesktop' / 'settings.dpapi'

    def load(self):
        if not self.path.exists():
            return DEFAULTS.copy()
        try:
            value = json.loads(crypt(self.path.read_bytes(), True))
            if not isinstance(value, dict):
                raise ValueError()
            result = DEFAULTS | {k:v for k,v in value.items() if k in DEFAULTS}
            if any(not isinstance(result[k],str) for k in ['key','persona','language']):
                raise ValueError()
            result['size'] = max(40,min(120,int(result['size'])))
            result['opacity'] = max(30,min(100,int(result['opacity'])))
            return result
        except AppError:
            raise
        except Exception:
            raise AppError('本地配置损坏，请备份后删除 settings.dpapi 并重新填写设置。') from None

    def save(self, settings):
        payload = crypt(json.dumps(settings, ensure_ascii=False).encode('utf-8'))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_bytes(payload)
        os.replace(temp,self.path)
