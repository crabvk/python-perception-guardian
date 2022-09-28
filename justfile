set dotenv-load

deploy:
    rsync -r --info=progress2 --filter=':- .gitignore' . $GUARDIAN_SERVER:~/perception-guardian

translations:
    poetry run python i18n-calls.py
