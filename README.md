# Perception Guardian

Telegram bot with image-emoji CAPTCHA challenge-response.

## TODO

* validate "Welcome message" markup
* check redis connection on startup and show warninig when "Connection refused"
* limit number of New Chat Members per minute, don't show captcha when limit has reached
* write custom middleware to support getting language by chat_id
* detect spam
* improve readme, add list of bot features section
* periodicly delete expired "ignore" set key/scores
* https://stackoverflow.com/questions/61419046/administrator-permissions-check-aiogram
* /stats command to show bot statistics: number of users passed/not passed captcha for group, etc.
* add more emoji

## Resources

* [Emoji Meanings Encyclopedia](https://emojis.wiki/)
* [Different kinds of UTF symbols representing letters](https://util.unicode.org/UnicodeJsps/list-unicodeset.jsp?a=[%3AIdn_Mapping%3Da%3A])
