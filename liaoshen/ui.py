import copy
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QIcon, QPixmap, QAction, QGuiApplication
from PySide6.QtWidgets import (QApplication,QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QLineEdit,QTextEdit,QComboBox,QSlider,QFormLayout,QDialogButtonBox,QSystemTrayIcon,QMenu,
    QScrollArea,QFrame,QMessageBox,QTableWidget,QTableWidgetItem,QHeaderView)
from .core import AppError,DeepSeek,context,language,Message,Snapshot
from .config import Config, DEFAULTS
from .reader import read_chat

STYLE = '''
QWidget {font-family: "Microsoft YaHei UI", "Noto Sans CJK SC", sans-serif; font-size:13px; color:#e7edf8;}
QWidget#panel, QDialog {background:#111827;}
QLabel {background:transparent;}
QLabel#brand {font-size:24px; font-weight:700; color:#a5f3fc;}
QLabel#section {font-size:15px; font-weight:600; color:#a5f3fc; padding-top:8px;}
QPushButton {background:#26354e; border:1px solid #3a4d6c; border-radius:9px; padding:9px 12px;}
QPushButton:hover {background:#354d70;} QPushButton:disabled {color:#718096; background:#202a3c;}
QPushButton#primary {background:#176f83; border-color:#2496a9;}
QLineEdit,QTextEdit,QComboBox,QTableWidget {background:#1c273b; border:1px solid #3b4b66; border-radius:6px; padding:6px; selection-background-color:#176f83;}
QComboBox QAbstractItemView {background:#1c273b; color:#e7edf8;}
QFrame#card {background:#1c273b; border:1px solid #3a4d6c; border-radius:12px;}
QScrollArea {border:none; background:transparent;} QScrollArea > QWidget > QWidget {background:#111827;}
QMenu {background:#1c273b;} QMenu::item:selected {background:#176f83;}
'''

def label(text='',name=None):
    w = QLabel(text)
    w.setWordWrap(True)
    w.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        w.setObjectName(name)
    return w

def robot(p,size):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('#123449'))
    p.drawEllipse(QRectF(1,1,size-2,size-2))
    p.setPen(QPen(QColor('#82e5e4'),size*.035))
    p.drawLine(QPoint(int(size*.5),int(size*.19)),QPoint(int(size*.5),int(size*.29)))
    p.setBrush(QColor('#9ff7f1'))
    p.drawRoundedRect(QRectF(size*.23,size*.30,size*.54,size*.43),size*.12,size*.12)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor('#103346'))
    for x in [.37,.63]:
        p.drawEllipse(QRectF(size*(x-.045),size*.43,size*.09,size*.12))
    p.setPen(QPen(QColor('#103346'),size*.025))
    p.drawLine(QPoint(int(size*.42),int(size*.63)),QPoint(int(size*.58),int(size*.63)))

def app_icon():
    pix = QPixmap(128,128)
    pix.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pix)
    robot(painter,128)
    painter.end()
    return QIcon(pix)

class Worker(QThread):
    result = Signal(object)
    error = Signal(str)
    def __init__(self,fn):
        super().__init__()
        self.fn=fn
    def run(self):
        try:
            self.result.emit(self.fn())
        except AppError as exc:
            self.error.emit(str(exc))
        except Exception:
            self.error.emit('操作未完成，返回数据或组件发生异常。请重试；悬浮窗仍可使用。')

class Settings(QDialog):
    def __init__(self,settings,parent):
        super().__init__(parent)
        self.setWindowTitle('聊神 · 设置')
        self.resize(470,460)
        self.settings=settings
        layout=QVBoxLayout(self)
        layout.addWidget(label('设置仅保存在当前 Windows 用户的本地加密配置中。'))
        form=QFormLayout()
        self.key=QLineEdit(settings['key'])
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow('DeepSeek API Key',self.key)
        self.persona=QTextEdit()
        self.persona.setPlainText(settings['persona'])
        self.persona.setMaximumHeight(110)
        form.addRow('我的人设',self.persona)
        self.lang=QComboBox()
        self.lang.addItems(['自动识别','Tiếng Việt','中文','English','日本語','한국어'])
        self.lang.setCurrentText(settings['language'])
        form.addRow('对方语言',self.lang)
        self.opacity=QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(30,100)
        self.opacity.setValue(settings['opacity'])
        form.addRow('悬浮图标透明度',self.opacity)
        self.size=QSlider(Qt.Orientation.Horizontal)
        self.size.setRange(40,120)
        self.size.setValue(settings['size'])
        form.addRow('悬浮图标大小',self.size)
        layout.addLayout(form)
        self.notice=label('仅手动读取当前聊天；确认后发送到 DeepSeek。不会自动发送微信消息。')
        layout.addWidget(self.notice)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('保存')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def save(self):
        value=dict(key=self.key.text().strip(),persona=self.persona.toPlainText(),language=self.lang.currentText(),opacity=self.opacity.value(),size=self.size.value())
        try:
            Config().save(value)
            self.settings.update(value)
            self.accept()
        except AppError as exc:
            self.notice.setText(str(exc))
        except OSError:
            self.notice.setText('配置无法写入，请检查本地磁盘空间和目录权限。')

class Review(QDialog):
    def __init__(self,snapshot,parent):
        super().__init__(parent)
        self.setWindowTitle('核对本次读取 · 确认后才发送给 DeepSeek')
        self.resize(650,580)
        self.original=snapshot
        layout=QVBoxLayout(self)
        layout.addWidget(label(f'{snapshot.source} · 置信度 {snapshot.confidence:.0%}\n{snapshot.warning}'))
        self.contact=QLineEdit(snapshot.contact)
        layout.addWidget(label('联系人（请核对，第一版只面向单人聊天）'))
        layout.addWidget(self.contact)
        self.table=QTableWidget(len(snapshot.messages),2)
        self.table.setHorizontalHeaderLabels(['发言人','原文（双击修改；非消息行可删除）'])
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for row,m in enumerate(snapshot.messages):
            side=QComboBox()
            side.addItems(['对方','我','不明'])
            side.setCurrentText(dict(other='对方',mine='我',unknown='不明')[m.side])
            self.table.setCellWidget(row,0,side)
            self.table.setItem(row,1,QTableWidgetItem(m.text))
        layout.addWidget(self.table)
        delete=QPushButton('删除选中行')
        delete.clicked.connect(self.remove)
        layout.addWidget(delete)
        self.hint=label('必须核对左右归属。保留“不明”的行不会提交；至少保留一条对方消息。只用于当前分析，不保存历史。')
        layout.addWidget(self.hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('已核对，分析这些消息')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.confirm)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    def remove(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()},reverse=True):
            self.table.removeRow(row)
    def confirm(self):
        messages=[]
        for row in range(self.table.rowCount()):
            side={'对方':'other','我':'mine','不明':'unknown'}[self.table.cellWidget(row,0).currentText()]
            text=self.table.item(row,1).text().strip()
            if text and side != 'unknown':
                messages.append(Message(text,side))
        if not any(m.side=='other' for m in messages) or not self.contact.text().strip() or self.contact.text().strip()=='联系人未识别':
            self.hint.setText('请填写联系人，并确认至少一条对方消息。')
            return
        self.snapshot=Snapshot(self.contact.text().strip(),messages,self.original.confidence,self.original.source,
                               self.original.warning+'；用户已核对，仍须考虑识别误差。')
        self.accept()

class ReplyCard(QFrame):
    clicked=Signal(int)
    def __init__(self,index):
        super().__init__()
        self.index=index
        self.setObjectName('card')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        box=QVBoxLayout(self)
        self.title=label(['温柔','直白','霸道'][index]+' · 点击整张卡片复制')
        self.fx=label('等待分析')
        self.zh=label()
        self.why=label()
        for w in [self.title,self.fx,self.zh,self.why]:
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            box.addWidget(w)
    def update_reply(self,r):
        self.fx.setText(r['fx'] or r['zh'])
        self.zh.setText('中文意思：'+r['zh'])
        self.why.setText('回复思路：'+r['why'])
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

class Panel(QWidget):
    def __init__(self,settings):
        super().__init__()
        self.settings=settings
        self.snapshot=None
        self.data=None
        self.analysis=None
        self.worker=None
        self.setObjectName('panel')
        self.setWindowTitle('聊神 · 桌面版')
        self.setWindowFlags(Qt.WindowType.Window|Qt.WindowType.WindowStaysOnTopHint)
        self.resize(520,820)
        layout=QVBoxLayout(self)
        top=QHBoxLayout()
        top.addWidget(label('聊神','brand'))
        top.addStretch()
        self.setting_btn=QPushButton('设置')
        self.setting_btn.clicked.connect(self.open_settings)
        top.addWidget(self.setting_btn)
        hide=QPushButton('收起')
        hide.clicked.connect(self.hide)
        top.addWidget(hide)
        layout.addLayout(top)
        layout.addWidget(label('读懂表达，认真回应。'))
        self.status=label('打开微信的单人聊天，点击“读取微信并分析”。')
        layout.addWidget(self.status)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        content=QWidget()
        self.body=QVBoxLayout(content)
        self.body.addWidget(label('01  对方消息 · 原文与翻译','section'))
        self.original=label('尚未读取')
        self.translation=label()
        self.body.addWidget(self.original)
        self.body.addWidget(self.translation)
        self.body.addWidget(label('02  AI 洞察','section'))
        self.facts=label('事实依据：本次核对的可见消息；不使用历史或联系人档案。')
        self.insight=label('情绪、意图、兴趣信号均为 AI 推测。')
        self.body.addWidget(self.facts)
        self.body.addWidget(self.insight)
        self.body.addWidget(label('03  三种回复 · 仅复制','section'))
        self.cards=[]
        for i in range(3):
            card=ReplyCard(i)
            card.clicked.connect(self.copy_reply)
            self.cards.append(card)
            self.body.addWidget(card)
        self.body.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.read_btn=QPushButton('读取微信并分析')
        self.read_btn.setObjectName('primary')
        self.read_btn.clicked.connect(self.read)
        layout.addWidget(self.read_btn)
        row=QHBoxLayout()
        self.reanalyze=QPushButton('重新分析')
        self.reanalyze.clicked.connect(self.analyze)
        self.choice=QComboBox()
        self.choice.addItems(['温柔','直白','霸道'])
        row.addWidget(self.reanalyze)
        row.addWidget(self.choice)
        self.short=QPushButton('短一点')
        self.gentle=QPushButton('再温柔一点')
        self.short.clicked.connect(lambda:self.rewrite('短一点'))
        self.gentle.clicked.connect(lambda:self.rewrite('再温柔一点'))
        row.addWidget(self.short)
        row.addWidget(self.gentle)
        layout.addLayout(row)
        layout.addWidget(label('不自动发送 · 不保存聊天记录 · 关闭面板后托盘常驻'))
        self.set_busy(False)
    def closeEvent(self,event):
        event.ignore()
        self.hide()
    def open_settings(self):
        if self.worker and self.worker.isRunning():
            self.status.setText('正在处理，请等当前操作结束后再修改设置。')
            return
        if Settings(self.settings,self).exec()==QDialog.DialogCode.Accepted:
            self.on_settings()
    def on_settings(self):
        pass
    def set_busy(self,busy):
        self.read_btn.setEnabled(not busy)
        self.setting_btn.setEnabled(not busy)
        self.reanalyze.setEnabled(not busy and self.snapshot is not None)
        for w in [self.short,self.gentle,self.choice]:
            w.setEnabled(not busy and self.data is not None)
        for card in self.cards:
            card.setEnabled(not busy and self.data is not None)
    def run(self,fn,done,text):
        if self.worker and self.worker.isRunning():
            return
        self.set_busy(True)
        self.status.setText(text)
        self.worker=Worker(fn)
        self.worker.result.connect(done)
        self.worker.error.connect(self.status.setText)
        self.worker.finished.connect(self.finished)
        self.worker.start()
    def finished(self):
        self.set_busy(False)
    def read(self):
        self.run(read_chat,self.review,'正在读取微信，最长等待 40 秒…')
    def review(self,snapshot):
        self.status.setText(f'{snapshot.source} · 置信度 {snapshot.confidence:.0%}'+ (' · 低置信度，请仔细核对' if snapshot.confidence<.75 else ' · 请核对'))
        dialog=Review(snapshot,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            self.status.setText('已取消，本次读取内容未发送到 DeepSeek。')
            return
        self.snapshot=dialog.snapshot
        self.data=None
        self.analysis=None
        self.original.setText('对方最新消息：\n'+next(m.text for m in reversed(self.snapshot.messages) if m.side=='other'))
        self.translation.setText('等待翻译')
        self.insight.setText('等待分析')
        self.facts.setText('事实依据（读取并经用户核对）：\n'+'\n'.join(f'[{"我" if m.side=="mine" else "对方"}] {m.text}' for m in self.snapshot.messages))
        for card in self.cards:
            card.fx.setText('等待分析')
            card.zh.clear()
            card.why.clear()
        # Start only after the previous reader worker has finished.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50,self.analyze)
    def analyze(self):
        if not self.snapshot:
            return
        settings=self.settings.copy()
        snapshot=copy.deepcopy(self.snapshot)
        def work():
            ai=DeepSeek(settings)
            user=context(snapshot,settings)
            main=ai.call('main',user)
            lang=language(snapshot,settings['language'])
            if lang!='中文' and any(not r['fx'].strip() for r in main['replies']):
                raise AppError('非中文回复缺少目标语言内容，请重新分析。')
            try:
                analysis=ai.call('analysis',user)
                error=''
            except AppError as exc:
                analysis=None
                error=str(exc)
            return main,analysis,error
        self.run(work,self.render,'正在请求 DeepSeek：翻译与三条回复，然后生成洞察…')
    def render(self,result):
        self.data,self.analysis,error=result
        self.translation.setText('中文翻译（对方最新消息）：'+(self.data['translation'] or '原文为中文，无需翻译。'))
        for card,r in zip(self.cards,self.data['replies']):
            card.update_reply(r)
        a=self.analysis
        if a:
            self.insight.setText('AI 推测（不代表对方真实想法）\n'+ '\n'.join(f'{name}：{a[key]}' for key,name in [('mood','情绪'),('intent','意图'),('attitude','态度'),('interest','兴趣程度'),('signal','信号强度'),('suggest','建议')])+'\n判断依据：以上本次可见消息；具体语气依据见情绪与意图说明。\n简要判断：'+self.data['psych'])
        else:
            self.insight.setText('简要判断（AI 推测）：'+self.data['psych']+'\n详细洞察未完成：'+error)
        low=' · 读取置信度低，请结合原文判断' if self.snapshot.confidence<.75 else ''
        self.status.setText(f'{self.snapshot.contact} · {self.snapshot.source} · {self.snapshot.confidence:.0%}'+low+(' · 部分洞察失败，可重新分析' if error else ' · 分析完成'))
    def copy_reply(self,index):
        if self.data:
            r=self.data['replies'][index]
            QApplication.clipboard().setText(r['fx'] or r['zh'])
            self.choice.setCurrentIndex(index)
            self.status.setText('已复制'+r['style']+'回复。请在微信自行粘贴、检查并发送。')
    def rewrite(self,how):
        if not self.data or not self.snapshot:
            return
        index=self.choice.currentIndex()
        old=self.data['replies'][index].copy()
        settings=self.settings.copy()
        snapshot=copy.deepcopy(self.snapshot)
        def work():
            lang=language(snapshot,settings['language'])
            user=context(snapshot,settings)+f'\n原回复（中文意思）：{old["zh"]}\n原回复（对方语言）：{old["fx"]}\n要求：{how}'
            new=DeepSeek(settings).call('rewrite',user)
            if lang!='中文' and not new['fx'].strip():
                raise AppError('改写缺少目标语言回复，已保留原卡片。')
            return new
        def done(new):
            # Atomic update: never retain a stale translation after rewriting.
            self.data['replies'][index]=dict(style=old['style'],**new)
            self.cards[index].update_reply(self.data['replies'][index])
            self.status.setText(f'已将{old["style"]}回复改为“{how}”，中文意思和回复思路同步更新。')
        self.run(work,done,'正在改写并同步中文意思…')

class FloatingBot(QWidget):
    def __init__(self,panel,settings):
        super().__init__()
        self.panel=panel
        self.settings=settings
        self.setWindowFlags(Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('聊神 · 单击展开/收起，拖动后自动吸边')
        self.apply()
        rect=QGuiApplication.primaryScreen().availableGeometry()
        self.move(rect.right()-self.width()+1,rect.center().y())
    def apply(self):
        self.setFixedSize(self.settings['size'],self.settings['size'])
        self.setWindowOpacity(self.settings['opacity']/100)
        self.update()
    def paintEvent(self,event):
        p=QPainter(self)
        robot(p,self.width())
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.start=event.globalPosition().toPoint()
            self.origin=self.pos()
            self.dragged=False
    def mouseMoveEvent(self,event):
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self,'start'):
            delta=event.globalPosition().toPoint()-self.start
            if delta.manhattanLength()>QApplication.startDragDistance():
                self.dragged=True
            if self.dragged:
                self.move(self.origin+delta)
    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton or not hasattr(self,'start'):
            return
        if self.dragged:
            screen=QGuiApplication.screenAt(event.globalPosition().toPoint()) or QGuiApplication.primaryScreen()
            rect=screen.availableGeometry()
            x=rect.left() if self.geometry().center().x()<rect.center().x() else rect.right()-self.width()+1
            self.move(x,max(rect.top(),min(self.y(),rect.bottom()-self.height()+1)))
        elif self.panel.isVisible():
            self.panel.hide()
        else:
            self.show_panel()
    def show_panel(self):
        rect=(QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()).availableGeometry()
        self.panel.resize(min(520,rect.width()),min(820,rect.height()))
        x=self.x()-self.panel.width()-10 if self.x()>rect.center().x() else self.x()+self.width()+10
        self.panel.move(max(rect.left(),min(x,rect.right()-self.panel.width()+1)),max(rect.top(),min(self.y(),rect.bottom()-self.panel.height()+1)))
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

class Controller:
    def __init__(self,app):
        self.app=app
        try:
            self.settings=Config().load()
            error=''
        except AppError as exc:
            self.settings=DEFAULTS.copy()
            error=str(exc)
        self.panel=Panel(self.settings)
        self.bot=FloatingBot(self.panel,self.settings)
        self.panel.on_settings=self.bot.apply
        self.bot.show()
        self.tray=QSystemTrayIcon(app_icon(),app)
        self.tray.setToolTip('聊神 · 点击悬浮机器人展开')
        menu=QMenu()
        for text,fn in [('打开面板',self.bot.show_panel),('设置',self.settings_dialog),('退出',self.quit)]:
            action=QAction(text,menu)
            action.triggered.connect(fn)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.bot.show_panel() if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()
        if error:
            self.panel.status.setText(error)
            self.bot.show_panel()
    def settings_dialog(self):
        self.bot.show_panel()
        self.panel.open_settings()
    def quit(self):
        # Requests have bounded timeouts; keep worker ownership until completion.
        worker=self.panel.worker
        if worker and worker.isRunning():
            self.bot.hide()
            self.panel.hide()
            self.tray.hide()
            worker.finished.connect(self.app.quit)
            self.panel.status.setText('正在退出，等待当前操作结束…')
        else:
            self.app.quit()
