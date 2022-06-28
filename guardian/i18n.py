import yaml
from pathlib import Path


class I18n:
    def __init__(self):
        t10s = {}
        files = Path(__file__).resolve().parent.parent.joinpath('i18n').glob('*.yaml')
        for f in files:
            with open(f, 'r') as stream:
                t10s |= yaml.safe_load(stream)
        self.t10s = t10s

    def t(self, lang: str, path: str, **kwargs):
        value = self.t10s[lang]
        for p in path.split('.'):
            value = value[p]
        if len(kwargs) > 0:
            return value.format(**kwargs)
        return value
