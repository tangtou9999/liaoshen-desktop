# Build on Windows x64 with CPython 3.11. Never embed local settings or API keys.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas=[('liaoshen/assets','liaoshen/assets')]
binaries=[]
hiddenimports=['win32gui','win32ui','win32process','pythoncom','pywintypes','comtypes.stream']
for package in ['rapidocr_onnxruntime','onnxruntime','uiautomation','comtypes']:
    d,b,h=collect_all(package)
    datas+=d
    binaries+=b
    hiddenimports+=h

a=Analysis(['main.py'],pathex=[],binaries=binaries,datas=datas,hiddenimports=hiddenimports,
           hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='LiaoShen',debug=False,bootloader_ignore_signals=False,
        strip=False,upx=False,console=False,disable_windowed_traceback=False,uac_admin=False)
