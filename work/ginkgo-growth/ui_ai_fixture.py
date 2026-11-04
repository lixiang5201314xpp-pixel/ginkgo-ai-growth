"""Own local UI fixture, synthetic account/content and mocked AI; no paid calls."""
from test_ai import Tests
test=Tests();test.setUp();test.ready();test.seed(alias='测试咨询')
test.e.start()
if __name__=='__main__':test.app.run('127.0.0.1',8818,debug=False)
