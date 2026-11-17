"""Offscreen Qt checks; these do not assert real Windows desktop behavior."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from liaoshen.ui import Panel, Review
from liaoshen.config import DEFAULTS
from liaoshen.core import Message,Snapshot,AppError

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.panel=Panel(DEFAULTS | dict(language='Tiếng Việt',key='test-only'))
        self.panel.snapshot=Snapshot('Linh',[Message('Xin chào','other')],.5,'test')
        self.old=dict(style='温柔',zh='旧中文',fx='old',why='旧思路')
        self.panel.data=dict(replies=[self.old.copy() for _ in range(3)])
    def tearDown(self):
        self.panel.deleteLater()
        self.app.processEvents()
    def test_rewrite_updates_both_and_copy(self):
        new=dict(zh='新中文',fx='new foreign',why='新思路')
        def synchronous(fn,done,text):
            done(fn())
        self.panel.run=synchronous
        with patch('liaoshen.ui.DeepSeek.call',return_value=new):
            self.panel.rewrite('短一点')
        self.assertEqual(self.panel.data['replies'][0],dict(style='温柔',**new))
        self.assertIn('新中文',self.panel.cards[0].zh.text())
        self.panel.copy_reply(0)
        self.assertEqual(QApplication.clipboard().text(),'new foreign')
        self.panel.data['replies'][0]=self.old.copy()
        with patch('liaoshen.ui.DeepSeek.call',return_value=dict(zh='新',fx='',why='')):
            with self.assertRaises(AppError):
                self.panel.rewrite('短一点')
        self.assertEqual(self.panel.data['replies'][0],self.old)
    def test_review_excludes_unknown_and_requires_other(self):
        snap=Snapshot('Linh',[Message('unknown','unknown'),Message('hello','other')],.4,'OCR')
        dialog=Review(snap,self.panel)
        dialog.confirm()
        self.assertEqual([m.text for m in dialog.snapshot.messages],['hello'])
        dialog.deleteLater()
