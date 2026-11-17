# 聊神 Windows 桌面版

## 下载 1.0 体验版

**[点击直接下载 LiaoShen.exe（Windows 10/11 x64，约 138 MB）](https://github.com/tangtou9999/liaoshen-desktop/releases/download/v1.0.0-preview/LiaoShen.exe)**

下载时保存到 `D:\聊神`，双击运行；不用解压，不用安装 Python。

[备用下载页](https://github.com/tangtou9999/liaoshen-desktop/releases/tag/v1.0.0-preview)。只需下载 `LiaoShen.exe`；源码是本仓库，不必逐个下载开发文件。

该体验版已通过兼容层启动检查；真实 Windows 10/11、真实微信读取和真实 DeepSeek 调用仍未测试。

独立的 Python + PySide6 项目，未修改安卓工程。五份提示词原样复制。

交付的 `LiaoShen.exe` 是 Windows x64 单文件软件，使用者无需 Python。直接运行说明见 [快速使用](快速使用.txt)，技术说明和测试限制见 [使用说明](使用说明.md)。

exe 已使用 Windows Python/PyInstaller 在 Wine 兼容层中构建并完成启动检查。真实 Windows 10/11、微信读屏和真实 DeepSeek 调用仍未测试。

- 入口：`main.py`
- Windows 重新构建：`build_windows.bat`
- 构建锁文件：`requirements-windows.lock.txt`
- 构建输出：`dist/LiaoShen.exe`
- 自动检查：`python -m unittest discover -s tests -v`
- 实际构建、归档核对和兼容层启动记录：`构建验证/`
