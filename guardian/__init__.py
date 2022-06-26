import sys
import argparse
import yaml
from pathlib import Path
from guardian.app import start_bot


class Config(dict):
    def __init__(self, d: dict):
        for k, v in d.items():
            if isinstance(v, dict):
                d[k] = Config(v)
        super(Config, self).__init__(d)
        self.__dict__ = self


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', default='config.yaml', help='Path to configuration file.')
    args = parser.parse_args()
    config_file = Path(args.config)

    if not config_file.is_absolute():
        config_file = Path(__file__).resolve().parent.parent.joinpath(config_file).resolve()

    if not config_file.is_file():
        print(f'File not found: {config_file}', file=sys.stderr)
        sys.exit(1)

    with open(config_file, 'r') as stream:
        config = yaml.safe_load(stream)
    start_bot(Config(config))


if __name__ == '__main__':
    cli()
