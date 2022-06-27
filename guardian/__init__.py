import sys
import argparse
import yaml
from pathlib import Path
from guardian.app import App
from guardian.config import Config


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
        config = Config(yaml.safe_load(stream))

    App(config).start()


if __name__ == '__main__':
    cli()
