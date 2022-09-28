import re
from pathlib import Path
from guardian.i18n import I18nMiddleware


LIGHT_GREEN = '\033[0;92m'
RESET = '\033[0m'


class I18nTest():
    def __init__(self):
        self.paths = set()

    def t(self, path: str):
        self.paths.add(path)


i18n = I18nTest()
files = Path(__file__).resolve().parent.joinpath('guardian').glob('*.py')
for f in files:
    with open(f, 'r') as stream:
        contents = stream.read()
    result = re.findall(r"""i18n\.t\((?:').*?(?:')""", contents, re.MULTILINE | re.DOTALL)
    for code in result:
        eval(code + ')')

translations = I18nMiddleware.load_translations()
for lang in translations.keys():
    for path in i18n.paths:
        print(f'{LIGHT_GREEN}{lang}.{path}{RESET}')
        value = translations[lang]
        for p in path.split('.'):
            value = value[p]
        print(value)
