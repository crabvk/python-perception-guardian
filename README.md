# Perception Guardian

Telegram bot with image-emoji CAPTCHA challenge-response.

<img src="example.png" alt="example" width="468" height="393"/>

## Features

* Show CAPTCHA for new members
* Ban channels [(optional)](#bot-settings)
* Change bot language for the group (only English and Russian supported at the time)
* Set custom Welcome message

## Configuration

Copy [config.example.yaml](config.example.yaml) to *config.yaml*. There are comments describing all the config settings.

## Bot settings

Use `/settings` command to change bot settings for the group.

## TODO

* log link to the image, all emoji variants and the chosen one
* validate "Welcome message" markup
* check redis connection on startup
* limit number of New Chat Members per minute, don't show captcha when limit has reached
* /vacuum command to search and delete "Deleted Account"s
* detect spam
* periodicly delete expired "ignore" set key/scores
* https://stackoverflow.com/questions/61419046/administrator-permissions-check-aiogram
* /stats command to show bot statistics: number of users passed/not passed captcha for group, etc.
* add more emoji

## Resources

* [Emoji Meanings Encyclopedia](https://emojis.wiki/)
* [Different kinds of UTF symbols representing letters](https://util.unicode.org/UnicodeJsps/list-unicodeset.jsp?a=[%3AIdn_Mapping%3Da%3A])
