# bashbridge

## Discord/Minecraft Chat Bridge for Linux Servers

This is a fairly simple Chat Bridge for a Minecraft server running on Linux (designed for RHEL 9) and a Discord text channel.

Rename the example config file to `config.ini` and edit the contents. This bridge should be started after your server is running, and stopped before your server is stopped.

## Features

Reads your minecraft server log. Chat messages, Player activity (join/leave/deaths/achievements), and Player actions (/me command) are extracted and posted to Discord with the player's username.

Reads your Discord channel, and posts the messages in the Minecraft server with the /say command in a light blue font color, with the Discord user's server nickname or display_name. It has the following features:
- When an image is posted, prepends the MC message with <image>
- When a message has an embed, appends the MC message with <embed>
- When a message is a reply, prepends the MC message with (reply @discord_nickname)
- When a message contains a link, replaces it with <example.com link>
- When a message @s another user, sanitizes the @ symbol with a (r)
- When a message contains emotes, their names are cleaned.
- When a message is longer than 250 characters, it is split up and each part is sent in MC individually.

## About

All you need is the python script and the config file (renamed). I recommend a python venv. I used Python 3.9. Install/upgrade pip and wheel, and install the requirements.txt. To make it run 24/7, set up the systemd service. Modify the .service file and place it in /etc/systemd/system, run `systemctl daemon-reload`, and then `systemctl enable --now bashbridge.service`. This assumes you already have a systemd service for the minecraft server itself.

If you have SELinux, install the .te file (you can ask ChatGPT or something how to do that -- checkmodule, semodule_package, and semanage).
 
I recommend using a restricted service account, separate from the minecraft server's service account. This account should be able to read the MC Server's files (via group membership), but the MC Server account should not be allowed to access the bashbridge files (for security depth).

You need to set up RCON on your minecraft server. It's just a few options in the server.properties.

You can look up how to create a Discord bot. it's pretty simple. It needs pretty basic permissions for sending messages and reading message contents. Invite it to your server, get your channel ID, and set it in the config, along with the bot account's token (which is the bot's account password, basically).
