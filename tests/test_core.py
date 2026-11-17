import json
import unittest
from unittest.mock import patch,Mock
import requests
from liaoshen.core import AppError,DeepSeek,extract_json,validate,context,Snapshot,Message
from liaoshen.reader import side_from_rect

MAIN=dict(translation='你好',psych='信息不足',stage=0,profile='',seg='',answer='',replies=[dict(style=s,zh='你好',fx='Xin chào',why='自然回应') for s in ['温柔','直白','霸道']])
class CoreTests(unittest.TestCase):
    def test_json_strings_and_fences(self):
        d={'a':'包含 } 和 " 引号','b':{'c':1}}
        for raw in [json.dumps(d),'```json\n'+json.dumps(d)+'\n```','结果：'+json.dumps(d)+' 结束']:
            self.assertEqual(extract_json(raw),d)
        with self.assertRaises(AppError):
            extract_json('{"a":')
    def test_schema_and_atomic_rewrite_precondition(self):
        validate(MAIN,'main')
        for invalid in [dict(zh='',fx='new',why=''),dict(fx='new',why=''),dict(zh=1,fx='new',why='')]:
            with self.assertRaises(AppError):
                validate(invalid,'rewrite')
        with self.assertRaises(AppError):
            validate(MAIN | dict(replies=[]),'main')
    def test_sender_geometry(self):
        self.assertEqual(side_from_rect(10,110,0,600),'other')
        self.assertEqual(side_from_rect(490,590,0,600),'mine')
        self.assertEqual(side_from_rect(0,600,0,600),'unknown')
        self.assertEqual(side_from_rect(250,350,0,600),'unknown')
    def test_context_keeps_roles(self):
        s=Snapshot('小明',[Message('a','mine'),Message('b','other')],.5,'OCR','可能有错')
        text=context(s,dict(language='中文',persona='真诚'))
        self.assertIn('[我] a',text)
        self.assertIn('[对方] b',text)
        self.assertIn('置信度 50%',text)
    @patch('liaoshen.core.requests.post')
    def test_request_protocol(self,post):
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={'choices':[{'message':{'content':json.dumps(MAIN)},'finish_reason':'stop'}]}
        self.assertEqual(DeepSeek({'key':'test-key'}).call('main','输入'),MAIN)
        kw=post.call_args.kwargs
        self.assertEqual(kw['timeout'],(15,60))
        self.assertEqual(kw['json']['max_tokens'],700)
        self.assertEqual(kw['json']['response_format'],{'type':'json_object'})
        self.assertEqual(kw['headers']['Authorization'],'Bearer test-key')
    @patch('liaoshen.core.requests.post')
    def test_errors_hide_server_body_and_secrets(self,post):
        for code in [400,401,402,403,404,422,429,500,503]:
            post.return_value=Mock(status_code=code,text='secret-key')
            with self.assertRaises(AppError) as ctx:
                DeepSeek({'key':'secret-key'}).call('main','输入')
            self.assertIn(str(code),str(ctx.exception))
            self.assertNotIn('secret-key',str(ctx.exception))
        post.side_effect=requests.Timeout()
        with self.assertRaisesRegex(AppError,'超时'):
            DeepSeek({'key':'x'}).call('main','输入')
        post.side_effect=None
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={}
        with self.assertRaisesRegex(AppError,'数据格式异常'):
            DeepSeek({'key':'x'}).call('main','输入')
    @patch('liaoshen.core.requests.post')
    def test_missing_key_never_requests(self,post):
        with self.assertRaises(AppError):
            DeepSeek({}).call('main','输入')
        post.assert_not_called()

if __name__=='__main__':
    unittest.main()
