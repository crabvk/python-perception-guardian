class Config(dict):
    def __init__(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                d[k] = Config(v)
        super(Config, self).__init__(d)
        self.__dict__ = self
