from ...core.tg_client import TgClient

user_settings_text = {
    "THUMBNAIL": (
        "Photo or Doc",
        "Custom Thumbnail is used as the thumbnail for the files you upload to telegram in media or document mode.",
        "<i>Send a photo to save it as custom thumbnail.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "RCLONE_CONFIG": (
        "",
        "",
        "<i>Send your <code>rclone.conf</code> file to use as your Upload Dest to RClone.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "TOKEN_PICKLE": (
        "",
        "",
        "<i>Send your <code>token.pickle</code> to use as your Upload Dest to GDrive</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "LEECH_SPLIT_SIZE": (
        "",
        "",
        f"Send Leech split size in bytes or use gb or mb. Example: 40000000 or 2.5gb or 1000mb. PREMIUM_USER: {TgClient.IS_PREMIUM_USER}.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "LEECH_DUMP_CHAT": (
        "",
        "",
        """Send leech destination ID/USERNAME/PM.
* b:id/@username/pm (b: means leech by bot) (id or username of the chat or write pm means private message so bot will send the files in private to you) when you should use b:(leech by bot)? When your default settings is leech by user and you want to leech by bot for specific task.
* u:id/@username(u: means leech by user) This incase OWNER added USER_STRING_SESSION.
* h:id/@username(hybrid leech) h: to upload files by bot and user based on file size.
* id/@username|topic_id(leech in specific chat and topic) add | without space and write topic id after chat id or username.
╰ <b>Time Left :</b> <code>60 sec</code>""",
    ),
    "LEECH_PREFIX": (
        "",
        "",
        "Send Leech Filename Prefix. You can add HTML tags. Example: <code>@mychannel</code>.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "LEECH_SUFFIX": (
        "",
        "",
        "Send Leech Filename Suffix. You can add HTML tags. Example: <code>@mychannel</code>.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "LEECH_CAPTION": (
        "",
        "",
        "Send Leech Caption. You can add HTML tags. Example: <code>@mychannel</code>.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "THUMBNAIL_LAYOUT": (
        "",
        "",
        "Send thumbnail layout (widthxheight, 2x2, 3x3, 2x4, 4x4, ...). Example: 3x3.</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "GRID_THUMBNAIL_LAYOUT": (
        "",
        "",
        "Send grid thumbnail layout (widthxheight, 2x3, 3x3, 3x2, ...). Example: 2x3 (2 columns, 3 rows = 6 frames).</i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "RCLONE_PATH": (
        "",
        "",
        "Send Rclone Path. If you want to use your rclone config edit using owner/user config from usetting or add mrcc: before rclone path. Example mrcc:remote:folder. </i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "RCLONE_FLAGS": (
        "",
        "",
        "key:value|key|key|key:value . Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>\n"
        "Ex: --buffer-size:8M|--drive-starred-only",
    ),
    "GDRIVE_ID": (
        "",
        "",
        "Send Gdrive ID. If you want to use your token.pickle edit using owner/user token from usetting or add mtp: before the id. Example: mtp:F435RGGRDXXXXXX . </i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "INDEX_URL": (
        "",
        "",
        "Send Index URL for your gdrive option. </i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "UPLOAD_PATHS": (
        "",
        "",
        "Send Dict of keys that have path values. Example: {'path 1': 'remote:rclonefolder', 'path 2': 'gdrive1 id', 'path 3': 'tg chat id', 'path 4': 'mrcc:remote:', 'path 5': b:@username} . </i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "EXCLUDED_EXTENSIONS": (
        "",
        "",
        "Send exluded extenions seperated by space without dot at beginning. </i>\n"
        "╰ <b>Time Left :</b> <code>60 sec</code>",
    ),
    "NAME_SWAP": (
        "",
        "",
        """<i>Send your Name Swap. You can add pattern instead of normal text according to the format.</i>
<b>Full Documentation Guide</b> <a href="https://t.me/WZML_X/77">Click Here</a>
╰ <b>Time Left :</b> <code>60 sec</code>
""",
    ),
    "YT_DLP_OPTIONS": (
        "",
        "",
        """Format: {key: value, key: value, key: value}.
Example: {"format": "bv*+mergeall[vcodec=none]", "nocheckcertificate": True, "playliststart": 10, "fragment_retries": float("inf"), "matchtitle": "S13", "writesubtitles": True, "live_from_start": True, "postprocessor_args": {"ffmpeg": ["-threads", "4"]}, "wait_for_video": (5, 100), "download_ranges": [{"start_time": 0, "end_time": 10}]}
Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official_channel/177'>script</a> to convert cli arguments to api options.
<i>Send dict of YT-DLP Options according to format.</i>
╰ <b>Time Left :</b> <code>60 sec</code>""",
    ),
    "FFMPEG_CMDS": (
        "",
        "",
        """Dict of list values of ffmpeg commands. You can set multiple ffmpeg commands for all files before upload. Don't write ffmpeg at beginning, start directly with the arguments.
Examples: {"subtitle": ["-i mltb.mkv -c copy -c:s srt mltb.mkv", "-i mltb.video -c copy -c:s srt mltb"], "convert": ["-i mltb.m4a -c:a libmp3lame -q:a 2 mltb.mp3", "-i mltb.audio -c:a libmp3lame -q:a 2 mltb.mp3"], extract: ["-i mltb -map 0:a -c copy mltb.mka -map 0:s -c copy mltb.srt"]}
Notes:
- Add `-del` to the list which you want from the bot to delete the original files after command run complete!
- To execute one of those lists in bot for example, you must use -ff subtitle (list key) or -ff convert (list key)
Here I will explain how to use mltb.* which is reference to files you want to work on.
1. First cmd: the input is mltb.mkv so this cmd will work only on mkv videos and the output is mltb.mkv also so all outputs is mkv. -del will delete the original media after complete run of the cmd.
2. Second cmd: the input is mltb.video so this cmd will work on all videos and the output is only mltb so the extenstion is same as input files.
3. Third cmd: the input in mltb.m4a so this cmd will work only on m4a audios and the output is mltb.mp3 so the output extension is mp3.
4. Fourth cmd: the input is mltb.audio so this cmd will work on all audios and the output is mltb.mp3 so the output extension is mp3.
<i>Send dict of FFMPEG_CMDS Options according to format.</i>
╰ <b>Time Left :</b> <code>60 sec</code>
""",
    ),
    "METADATA_CMDS": ( # Uncomment if METADATA_CMDS is used elsewhere
        "",
        "",
        """<i>Send your Meta data. You can according to the format title="Join @WZML_X".</i>
<b>Full Documentation Guide</b> <a href="https://t.me/WZML_X/">Click Here</a>
╰ <b>Time Left :</b> <code>60 sec</code>
""",
    ),
    "USER_COOKIE_FILE": (
        "File",
        "User's YT-DLP Cookie File to authenticate access to websites and youtube.",
        "<i>Send your cookie file (e.g., cookies.txt).</i>\n"
        "<b>Time Left :</b> <code>60 sec</code>",
    ),
    "LEECH_FILENAME_CAPTION": """Send leech filename caption with template variables. Timeout: 60 sec

- <code>{filename}</code>: Original filename with extension
- <code>{file_caption}</code>: Custom caption text (if set)
- <code>{languages}</code>: Audio languages detected (comma-separated)
- <code>{subtitles}</code>: Subtitle languages detected (comma-separated)
- <code>{duration}</code>: Media duration (HH:MM:SS format)
- <code>{resolution}</code>: Video resolution (e.g., 1080p, 720p, 4K)
- <code>{audio}</code>: Audio codec and channels (e.g., AAC 2.0, AC3 5.1)
- <code>{name}</code>: Movie/TV show title from IMDB
- <code>{year}</code>: Release year from IMDB
- <code>{quality}</code>: Detected quality (1080p, 720p, 2160p, etc.)
- <code>{season}</code>: Season number (S01, S02, etc.)
- <code>{episode}</code>: Episode number (E01, E02, etc.)
- <code>{ott}</code>: OTT platform tag (if detected)
- <code>{size}</code>
- <code>{md5_hash}</code>: MD5 checksum of the file
<b>Example Templates:</b>
1. <code>📁 {filename}\n💾 Size: {filesize}\n⏱ Duration: {duration}</code>
2. <code>{name} ({year}) - {quality}\n🎬 {filename} | {filesize}</code>
3. <code>🎥 {filename}\n🔊 Audio: {languages}\n📝 Subs: {subtitles}</code>
4. <code>{name} S{season}E{episode} [{quality} {audio}]\n💾 {filesize} | ⏱ {duration}</code>""",
    "AUTO_RENAME": """Enable or disable automatic file renaming with IMDB integration.
When enabled:
- Fetches metadata from IMDB (title, year, rating, genres, poster)
- Detects media quality (resolution, codec, audio)
- Handles multi-resolution batches intelligently
- Tracks episode numbers for TV shows
- Applies custom rename template to files

Template Variables: {name}, {year}, {quality}, {season}, {episode}, {audio}
Example template: <code>{name} ({year}) S{season}E{episode} {quality} {audio}</code>
Result: <code>Breaking Bad (2008) S01E01 1080p AAC 5.1</code>""",
    "RENAME_TEMPLATE": """Customize the auto-rename filename template.
Available variables:
- <code>{name}</code>: Title from IMDB (Movie/TV Show name)
- <code>{year}</code>: Release year from IMDB
- <code>{quality}</code>: Detected quality (1080p, 720p, 2160p, etc.)
- <code>{season}</code>: Season number (S01, S02, etc.)
- <code>{episode}</code>: Episode number (E01, E02, etc.)
- <code>{audio}</code>: Audio codec with channels (AAC 2.0, AC3 5.1, etc.)

Example Templates:
1. <code>{name} ({year}) S{season}E{episode} {quality} {audio}</code>
2. <code>{name} {year} {quality}</code>
3. <code>[{quality}] {name} - {season}{episode}</code>
4. <code>{name} S{season}E{episode} [{quality} {audio}]</code>

Must contain at least one variable. Timeout: 60 sec""",
    "START_EPISODE": """Set the starting episode number for TV show renaming.
When processing TV episodes, the counter will start from this number.
Example: Set to 5 to start naming episodes as E05, E06, E07...

Valid range: 1 to 9999
Default: 1
Timeout: 60 sec""",
    "START_SEASON": """Set the starting season number for TV show renaming.
When processing TV shows, the season will be labeled with this number.
Example: Set to 2 to name episodes as S02E01, S02E02...

Valid range: 1 to 99
Default: 1
Timeout: 60 sec""",




}
