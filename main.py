import multiprocessing
import sys

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtCore import QIODevice
    from liaoshen.ui import Controller, STYLE, app_icon
    # The custom dark interface uses its own palette, independent of WinRT accents.
    QApplication.setDesktopSettingsAware(False)
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName('LiaoShenDesktop')
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)
    app.setWindowIcon(app_icon())
    socket=QLocalSocket()
    socket.connectToServer('LiaoShenDesktop-v1',QIODevice.OpenModeFlag.WriteOnly)
    if socket.waitForConnected(300):
        socket.write(b'open')
        socket.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer('LiaoShenDesktop-v1')
    server=QLocalServer()
    if not server.listen('LiaoShenDesktop-v1'):
        QMessageBox.warning(None,'聊神','无法创建本地单实例服务，请稍后重试。')
        return 1
    controller=Controller(app)
    def open_existing():
        connection=server.nextPendingConnection()
        if connection:
            connection.close()
            connection.deleteLater()
        controller.bot.show_panel()
    server.newConnection.connect(open_existing)
    return app.exec()

if __name__=='__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
