set dotenv-load

deploy:
    rsync -r --info=progress2 --filter=':- .gitignore' . $GUARDIAN_SERVER:~/perception-guardian
