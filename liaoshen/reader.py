"""Read-only WeChat adapter. Never focuses, types, clicks, sends or modifies WeChat."""
import os
import time
import multiprocessing as mp
from .core import AppError, Message, Snapshot


def side_from_rect(left, right, area_left, area_right):
    width = area_right - area_left
    if width <= 0 or right-left > width * .80:
        return 'unknown'
    # Bubble bounding boxes, not full-width ListItem rectangles.
    dl, dr = left-area_left, area_right-right
    if abs(dl-dr) < width * .13:
        return 'unknown'
    return 'other' if dl < dr else 'mine'


def walk(control, depth=0):
    if depth > 12:
        return
    yield control
    for child in control.GetChildren():
        yield from walk(child, depth+1)


def find_wechat():
    import win32gui
    import win32process
    import psutil
    windows = []
    def visit(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return
        try:
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            exe = psutil.Process(pid).name().lower()
            rect = win32gui.GetWindowRect(hwnd)
            if exe in ('wechat.exe','weixin.exe') and rect[2]-rect[0] > 450 and rect[3]-rect[1] > 350:
                windows.append((hwnd,win32gui.GetWindowText(hwnd)))
        except (psutil.Error, OSError):
            pass
    win32gui.EnumWindows(visit,None)
    if not windows:
        raise AppError('未找到可见的微信聊天窗口。请打开微信并进入具体聊天，保持窗口未最小化。')
    # Multiple visible sessions must not silently select a different contact.
    if len(windows) > 1:
        raise AppError('找到多个微信窗口。请最小化其他微信窗口，只保留要读取的聊天窗口。')
    return windows[0]


def uia_read(hwnd, title):
    import uiautomation as auto
    with auto.UIAutomationInitializerInThread():
        auto.SetGlobalSearchTimeout(2)
        root = auto.ControlFromHandle(hwnd)
        controls = list(walk(root))[:5000]
        lists = [c for c in controls if c.ControlTypeName == 'ListControl' and c.Name.strip() in ('消息','消息列表','Messages','Chat messages')]
        if not lists:
            return None, None
        area = lists[-1].BoundingRectangle
        bounds = (area.left,area.top,area.right,area.bottom)
        if area.width() <= 0 or area.height() <= 0:
            return None,None
        contact = title if title not in ('微信','WeChat','Weixin','微信 (WeChat)') else ''
        # Title in header above the message list, never left sidebar contacts.
        headers = []
        for c in controls:
            r = c.BoundingRectangle
            if c.ControlTypeName == 'TextControl' and c.Name.strip() and area.left <= r.left < area.right and area.top-100 <= r.top < area.top:
                if c.Name.strip() not in ('聊天信息','搜索','Search'):
                    headers.append((r.top,c.Name.strip()))
        if headers:
            contact = sorted(headers)[0][1]
        messages = []
        for item in lists[-1].GetChildren()[-40:]:
            if item.ControlTypeName != 'ListItemControl':
                continue
            nodes = list(walk(item))
            texts = []
            for n in nodes[1:]:
                if n.ControlTypeName == 'TextControl' and n.Name.strip():
                    r = n.BoundingRectangle
                    if r.bottom <= area.top or r.top >= area.bottom:
                        continue
                    texts.append((n.Name.strip(),r))
            if not texts:
                # Unknown structure: keep text but require explicit sender correction.
                if item.Name.strip():
                    messages.append(Message(item.Name.strip(),'unknown'))
                continue
            # Avatar buttons provide stronger alignment than the message text itself.
            avatars = [n for n in nodes[1:] if n.ControlTypeName == 'ButtonControl' and 20 <= n.BoundingRectangle.width() <= 65 and 20 <= n.BoundingRectangle.height() <= 65]
            side = 'unknown'
            if len(avatars) == 1:
                r = avatars[0].BoundingRectangle
                side = side_from_rect(r.left,r.right,area.left,area.right)
            if side == 'unknown':
                left = min(r.left for _,r in texts)
                right = max(r.right for _,r in texts)
                side = side_from_rect(left,right,area.left,area.right)
            messages.append(Message('\n'.join(t for t,_ in texts),side))
        if not messages:
            return None,bounds
        unknown = sum(m.side == 'unknown' for m in messages)
        confidence = .82 if contact and not unknown else .50
        return Snapshot(contact or '联系人未识别',messages[-30:],confidence,'Windows UI Automation',
                        '发言人按头像或气泡位置判断，必须核对；群聊、图片、语音和特殊消息不保证完整。'),bounds


def capture_window(hwnd):
    import ctypes
    from ctypes import wintypes
    import win32gui
    import win32ui
    from PIL import Image, ImageStat
    left,top,right,bottom = win32gui.GetWindowRect(hwnd)
    w,h = right-left,bottom-top
    hdc = win32gui.GetWindowDC(hwnd)
    src = win32ui.CreateDCFromHandle(hdc)
    dst = src.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    try:
        bitmap.CreateCompatibleBitmap(src,w,h)
        dst.SelectObject(bitmap)
        print_window = ctypes.windll.user32.PrintWindow
        print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        print_window.restype = wintypes.BOOL
        if not print_window(hwnd,dst.GetSafeHdc(),2):
            raise AppError('微信窗口截图失败。请保持微信可见，稍后重试。')
        image = Image.frombuffer('RGB',(w,h),bitmap.GetBitmapBits(True),'raw','BGRX',0,1).copy()
        if max(ImageStat.Stat(image).stddev) < 2:
            raise AppError('微信截图为空白（可能受窗口渲染或保护限制），请调整窗口后重试。')
        return image,(left,top,right,bottom)
    finally:
        dst.DeleteDC()
        src.DeleteDC()
        win32gui.ReleaseDC(hwnd,hdc)
        win32gui.DeleteObject(bitmap.GetHandle())


def ocr_read(hwnd,title,bounds):
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    image,window = capture_window(hwnd)
    w,h = image.size
    if bounds:
        x1,y1,x2,y2 = bounds
        crop = (max(0,x1-window[0]),max(0,y1-window[1]),min(w,x2-window[0]),min(h,y2-window[1]))
    else:
        # Conventional PC layout only. Always marked low-confidence and reviewed.
        crop = (int(w*.36),int(h*.15),w-15,int(h*.77))
    if crop[2] <= crop[0] or crop[3] <= crop[1]:
        raise AppError('聊天区域位置异常，请调整微信窗口大小后重试。')
    region = image.crop(crop)
    results,_ = RapidOCR()(np.asarray(region))
    if not results:
        raise AppError('UI Automation 和 OCR 均未读到消息。请打开具体聊天并调整窗口大小。')
    messages,scores = [],[]
    for box,text,score in sorted(results,key=lambda r:min(p[1] for p in r[0])):
        if not text.strip():
            continue
        left,right = min(p[0] for p in box),max(p[0] for p in box)
        side = side_from_rect(left,right,0,region.width)
        messages.append(Message(text.strip(),side))
        scores.append(float(score))
    return Snapshot(title if title not in ('微信','WeChat','Weixin') else '联系人未识别',messages[-30:],
                    min(.59,sum(scores)/max(1,len(scores))), '窗口截图 OCR',
                    '低置信度：OCR 可能分行、漏字、混入界面文字；越南语声调可能识别不准。聊天区域及左右归属为推测，请逐条核对、删除非消息行并填写联系人。截图仅在内存处理。')


def _child(conn):
    try:
        if os.name != 'nt':
            raise AppError('读取微信仅支持 Windows 10/11。当前系统无法测试此功能。')
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        hwnd,title = find_wechat()
        bounds = None
        try:
            snapshot,bounds = uia_read(hwnd,title)
        except Exception:
            snapshot = None
        if snapshot is None or snapshot.confidence < .60:
            try:
                snapshot = ocr_read(hwnd,title,bounds)
            except Exception:
                if snapshot is None:
                    raise
                snapshot.warning += ' OCR 回退失败，请手动核对 UIA 结果。'
        conn.send(('ok',snapshot))
    except AppError as exc:
        conn.send(('error',str(exc)))
    except Exception:
        conn.send(('error','微信读取失败。可能是微信版本不兼容、权限不一致或 OCR 组件异常。请以同一用户权限启动并重试。'))
    finally:
        conn.close()


def read_chat():
    # Hard isolation prevents a stuck UIA provider/OCR from freezing the desktop app.
    ctx = mp.get_context('spawn')
    parent,child = ctx.Pipe(False)
    process = ctx.Process(target=_child,args=(child,),daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(40):
            raise AppError('读取微信超过 40 秒，已停止。请调整聊天窗口后重试。')
        status,value = parent.recv()
        if status != 'ok':
            raise AppError(value)
        return value
    except EOFError:
        raise AppError('读取组件意外结束，请重试。') from None
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=2)
