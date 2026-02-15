from asyncio import sleep
from functools import partial
from html import escape
from io import BytesIO
from os import getcwd
from re import sub, match as re_match
from time import time
from aiofiles.os import makedirs, remove
from aiofiles.os import path as aiopath
from langcodes import Language # Ensure langcodes is installed: pip install langcodes
from pyrogram.filters import create
from pyrogram.handlers import MessageHandler
from bot.helper.ext_utils.status_utils import get_readable_file_size
from .. import auth_chats, excluded_extensions, sudo_users, user_data
from ..core.config_manager import Config
from ..core.tg_client import TgClient
from ..helper.ext_utils.bot_utils import (
    get_size_bytes,
    new_task,
    update_user_ldata,
)
from ..helper.ext_utils.db_handler import database
from ..helper.ext_utils.media_utils import create_thumb
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telly_utils.help_messages import user_settings_text
from ..helper.telegram_helper.message_utils import (
    delete_message,
    edit_message,
    send_file,
    send_message,
)
handler_dict = {}
no_thumb = "https://ibb.co/Ng04vGdM"
leech_options = [
    "LEECH_SPLIT_SIZE",
    "LEECH_DUMP_CHAT",
    "LEECH_PREFIX",
    "LEECH_SUFFIX",
    "LEECH_CAPTION",
]
thumb_options = [
    "THUMBNAIL",
    "THUMBNAIL_LAYOUT",
    "USE_GRID_THUMBNAIL",
    "GRID_THUMBNAIL_LAYOUT",
]
tmdb_options = [
    "AUTO_THUMBNAIL",
    "TMDB_API_KEY",
    "TMDB_ENABLED",
    "IMDB_ENABLED",
    "TMDB_LANGUAGE",
    "TMDB_ADULT_CONTENT",
]
rclone_options = [
    "RCLONE_CONFIG", 
    "RCLONE_PATH", 
    "RCLONE_FLAGS"
    ]
gdrive_options = [
    "TOKEN_PICKLE", 
    "GDRIVE_ID", 
    "INDEX_URL"
    ]
ffset_options = [
    "FFMPEG_CMDS"
    ]
advanced_options = [
    "EXCLUDED_EXTENSIONS",
    "NAME_SWAP",
    "YT_DLP_OPTIONS",
    "UPLOAD_PATHS",
    "USER_COOKIE_FILE",
]
rename_options = [
    "AUTO_RENAME",
    "RENAME_TEMPLATE",
    "START_EPISODE",
    "START_SEASON",
]
async def get_user_settings(from_user, stype="main"):
    user_id = from_user.id
    user_name = from_user.mention(style="html")
    buttons = ButtonMaker()
    rclone_conf = f"rclone/{user_id}.conf"
    token_pickle = f"tokens/{user_id}.pickle"
    user_dict = user_data.get(user_id, {})
    thumbpath = f"thumbnails/{user_id}.jpg"
    thumbnail = thumbpath if await aiopath.exists(thumbpath) else no_thumb
    if stype == "main":
        buttons.data_button("General Settings", f"userset {user_id} general", position="header")
        buttons.data_button("Mirror Settings", f"userset {user_id} mirror")
        buttons.data_button("Leech Settings", f"userset {user_id} leech")
        buttons.data_button("Thumbnails Option", f"userset {user_id} thumb_options")
        buttons.data_button("FF Media Settings", f"userset {user_id} ffset")
        buttons.data_button("Misc Settings", f"userset {user_id} advanced", position="l_body")
        buttons.data_button("Auto Leech/Mirror", f"userset {user_id} auto_process", position="l_body")
        buttons.data_button("Auto Rename", f"userset {user_id} auto_rename", position="l_body")
        if user_dict and any(
            key in user_dict
            for key in list(user_settings_text.keys())
            + [
                "USER_TOKENS",
                "AS_DOCUMENT",
                "EQUAL_SPLITS",
                "MEDIA_GROUP",
                "USER_TRANSMISSION",
                "HYBRID_LEECH",
                "STOP_DUPLICATE",
                "DEFAULT_UPLOAD",
                # Add other potentially user-settable keys here if they aren't in user_settings_text
            ]
        ):
        # add auto rename and thumnail status
            buttons.data_button("Reset All", f"userset {user_id} reset all", position="footer")
        buttons.data_button("✘", f"userset {user_id} close", position="footer")
        # Status indicators
        auto_rename_status = ("Enabled" if user_dict.get("AUTO_RENAME", False) else "Disabled")
        auto_thumbnail_status = ("Enabled" if user_dict.get("TMDB_ENABLED", False) else "Disabled")        
        rename_template = user_dict.get("RENAME_TEMPLATE", "S{season}E{episode}Q{quality}")
        thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"        
        text = f"""⌬ <b>User Settings :</b>
╭ <b>Name</b> → {user_name}
┊ <b>UserID</b> → #ID{user_id}
┊ <b>Username</b> → @{from_user.username}
┊ <b>Telegram DC</b> → {from_user.dc_id}
┊ <b>Telegram Lang</b> → {Language.get(lc).display_name() if (lc := from_user.language_code) else "N/A"}
┊ <b>Auto Rename</b> → {auto_rename_status}
┊ <b>Rename Template</b> → <code>{rename_template}</code>
┊ <b>Auto Thumbnail</b> → {auto_thumbnail_status}
╰ <b>Custom Thumbnail</b> → {thumbmsg}
"""
        btns = buttons.build_menu(2)
    elif stype == "general":
        if user_dict.get("DEFAULT_UPLOAD", ""):
            default_upload = user_dict["DEFAULT_UPLOAD"]
        elif "DEFAULT_UPLOAD" not in user_dict:
            default_upload = Config.DEFAULT_UPLOAD
        du = "GDRIVE API" if default_upload == "gd" else "RCLONE"
        dur = "GDRIVE API" if default_upload != "gd" else "RCLONE"
        buttons.data_button(
            f"Swap to {dur} Mode", f"userset {user_id} {default_upload}"
        )
        user_tokens = user_dict.get("USER_TOKENS", False)
        tr = "USER" if user_tokens else "OWNER"
        trr = "OWNER" if user_tokens else "USER"
        buttons.data_button(
            f"Swap to {trr} token/config",
            f"userset {user_id} tog USER_TOKENS {'f' if user_tokens else 't'}",
        )
        buttons.data_button("❰", f"userset {user_id} back", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")        
        use_user_cookie = user_dict.get("USE_USER_COOKIE", False)
        cookie_mode = "USER's" if use_user_cookie else "OWNER's"
        buttons.data_button(
            f"Swap to {'OWNER' if use_user_cookie else 'USER'}'s Cookie",
            f"userset {user_id} tog USE_USER_COOKIE {'f' if use_user_cookie else 't'}",
        )
        btns = buttons.build_menu(1)
        text = f"""⌬ <b>General Settings :</b>
╭ <b>Name</b> → {user_name}
┊ <b>Default Upload Package</b> → <b>{du}</b>
┊ <b>Default Usage Mode</b> → <b>{tr}'s</b> token/config
╰ <b>Cookie Mode</b> → <b>{cookie_mode}</b>
"""
    elif stype == "leech":
        buttons.data_button(
            "Leech Split Size", f"userset {user_id} menu LEECH_SPLIT_SIZE"
        )
        if user_dict.get("LEECH_SPLIT_SIZE", False):
            split_size = user_dict["LEECH_SPLIT_SIZE"]
        else:
            split_size = Config.LEECH_SPLIT_SIZE
        buttons.data_button(
            "Leech Destination", f"userset {user_id} menu LEECH_DUMP_CHAT"
        )
        if user_dict.get("LEECH_DUMP_CHAT", False):
            leech_dest = user_dict["LEECH_DUMP_CHAT"]
        elif "LEECH_DUMP_CHAT" not in user_dict and Config.LEECH_DUMP_CHAT:
            leech_dest = Config.LEECH_DUMP_CHAT
        else:
            leech_dest = "None"
        buttons.data_button("Leech Prefix", f"userset {user_id} menu LEECH_PREFIX")
        if user_dict.get("LEECH_PREFIX", False):
            lprefix = user_dict["LEECH_PREFIX"]
        elif "LEECH_PREFIX" not in user_dict and Config.LEECH_PREFIX:
            lprefix = Config.LEECH_PREFIX
        else:
            lprefix = "Not Exists"
        buttons.data_button("Leech Suffix", f"userset {user_id} menu LEECH_SUFFIX")
        if user_dict.get("LEECH_SUFFIX", False):
            lsuffix = user_dict["LEECH_SUFFIX"]
        elif "LEECH_SUFFIX" not in user_dict and Config.LEECH_SUFFIX:
            lsuffix = Config.LEECH_SUFFIX
        else:
            lsuffix = "Not Exists"
        buttons.data_button("Leech Caption", f"userset {user_id} menu LEECH_CAPTION")
        if user_dict.get("LEECH_CAPTION", False):
            lcap = user_dict["LEECH_CAPTION"]
        elif "LEECH_CAPTION" not in user_dict and Config.LEECH_CAPTION:
            lcap = Config.LEECH_CAPTION
        else:
            lcap = "Not Exists"

        if (
            user_dict.get("AS_DOCUMENT", False)
            or "AS_DOCUMENT" not in user_dict
            and Config.AS_DOCUMENT
        ):
            ltype = "DOCUMENT"
            buttons.data_button("Send As Media", f"userset {user_id} tog AS_DOCUMENT f")
        else:
            ltype = "MEDIA"
            buttons.data_button(
                "Send As Document", f"userset {user_id} tog AS_DOCUMENT t"
            )
        if (
            user_dict.get("EQUAL_SPLITS", False)
            or "EQUAL_SPLITS" not in user_dict
            and Config.EQUAL_SPLITS
        ):
            buttons.data_button(
                "Disable Equal Splits", f"userset {user_id} tog EQUAL_SPLITS f"
            )
            equal_splits = "Enabled"
        else:
            buttons.data_button(
                "Enable Equal Splits", f"userset {user_id} tog EQUAL_SPLITS t"
            )
            equal_splits = "Disabled"

        if (
            user_dict.get("MEDIA_GROUP", False)
            or "MEDIA_GROUP" not in user_dict
            and Config.MEDIA_GROUP
        ):
            buttons.data_button(
                "Disable Media Group", f"userset {user_id} tog MEDIA_GROUP f"
            )
            media_group = "Enabled"
        else:
            buttons.data_button(
                "Enable Media Group", f"userset {user_id} tog MEDIA_GROUP t"
            )
            media_group = "Disabled"
        if (
            TgClient.IS_PREMIUM_USER
            and user_dict.get("USER_TRANSMISSION", False)
            or "USER_TRANSMISSION" not in user_dict
            and Config.USER_TRANSMISSION
        ):
            buttons.data_button(
                "Leech by Bot", f"userset {user_id} tog USER_TRANSMISSION f"
            )
            leech_method = "user"
        elif TgClient.IS_PREMIUM_USER:
            leech_method = "bot"
            buttons.data_button(
                "Leech by User", f"userset {user_id} tog USER_TRANSMISSION t"
            )
        else:
            leech_method = "bot"

        if (
            TgClient.IS_PREMIUM_USER
            and user_dict.get("HYBRID_LEECH", False)
            or "HYBRID_LEECH" not in user_dict
            and Config.HYBRID_LEECH
        ):
            hybrid_leech = "Enabled"
            buttons.data_button(
                "Disable Hybride Leech", f"userset {user_id} tog HYBRID_LEECH f"
            )
        elif TgClient.IS_PREMIUM_USER:
            hybrid_leech = "Disabled"
            buttons.data_button(
                "Enable HYBRID Leech", f"userset {user_id} tog HYBRID_LEECH t"
            )
        else:
            hybrid_leech = "Disabled"
        buttons.data_button("❰", f"userset {user_id} back", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        btns = buttons.build_menu(2)
        text = f"""⌬ <b>Leech Settings :</b>
╭ <b>Name</b> → {user_name}
┊ Leech Type → <b>{ltype}</b>
┊ Leech Split Size → <b>{get_readable_file_size(split_size)}</b>
┊ Equal Splits → <b>{equal_splits}</b>
┊ Media Group → <b>{media_group}</b>
┊ Leech Prefix → <code>{escape(lprefix)}</code>
┊ Leech Suffix → <code>{escape(lsuffix)}</code>
┊ Leech Caption → <code>{escape(lcap)}</code>
┊ Leech Destination → <code>{leech_dest}</code>
┊ Leech by <b>{leech_method}</b> session
╰ Mixed Leech → <b>{hybrid_leech}</b>
"""
    elif stype == "thumb_options":
        # NEW: Thumbnails Options Sub-Menu
        thumbpath = f"thumbnails/{user_id}.jpg"
        thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"
        buttons.data_button("Set Thumbnail", f"userset {user_id} menu THUMBNAIL")
        buttons.data_button("Thumbnail Layout", f"userset {user_id} menu THUMBNAIL_LAYOUT")
        if user_dict.get("THUMBNAIL_LAYOUT", False):
            thumb_layout = user_dict["THUMBNAIL_LAYOUT"]
        elif "THUMBNAIL_LAYOUT" not in user_dict and Config.THUMBNAIL_LAYOUT:
            thumb_layout = Config.THUMBNAIL_LAYOUT
        else:
            thumb_layout = "None"
        # Grid Thumbnail Toggle
        if (
            user_dict.get("USE_GRID_THUMBNAIL", False)
            or "USE_GRID_THUMBNAIL" not in user_dict
            and Config.USE_GRID_THUMBNAIL
        ):
            buttons.data_button(
                "✘ Grid Thumbnail", f"userset {user_id} tog USE_GRID_THUMBNAIL f"
            )
            grid_thumb = "Enabled"
        else:
            buttons.data_button(
                "✓ Grid Thumbnail", f"userset {user_id} tog USE_GRID_THUMBNAIL t"
            )
            grid_thumb = "Disabled"
        # Grid Layout (only show if grid is enabled)
        if grid_thumb == "Enabled":
            buttons.data_button(
                "Grid Layout", f"userset {user_id} menu GRID_THUMBNAIL_LAYOUT"
            )
            if user_dict.get("GRID_THUMBNAIL_LAYOUT", False):
                grid_layout = user_dict["GRID_THUMBNAIL_LAYOUT"]
            elif "GRID_THUMBNAIL_LAYOUT" not in user_dict and Config.GRID_THUMBNAIL_LAYOUT:
                grid_layout = Config.GRID_THUMBNAIL_LAYOUT
            else:
                grid_layout = "2x3"
        else:
            grid_layout = "N/A"
        buttons.data_button("TMDB Settings", f"userset {user_id} tmdb")
        buttons.data_button("❰", f"userset {user_id} leech", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")

        btns = buttons.build_menu(2)
        text = f"""⌬ <b>Thumbnails Settings :</b>
╭ <b>Name</b> → {user_name}
┊ Custom Thumbnail → <b>{thumbmsg}</b>
┊ Thumbnail Layout → <b>{thumb_layout}</b>
┊ Grid Thumbnail → <b>{grid_thumb}</b>
╰ Grid Layout → <b>{grid_layout}</b>
"""
    elif stype == "tmdb":
        # Auto Thumbnail Toggle
        if (
            user_dict.get("AUTO_THUMBNAIL", False)
            or "AUTO_THUMBNAIL" not in user_dict
            and Config.AUTO_THUMBNAIL
        ):
            buttons.data_button(
                "✘ Auto Thumbnail", f"userset {user_id} tog AUTO_THUMBNAIL f"
            )
            auto_thumb = "Enabled"
        else:
            buttons.data_button(
                "✓ Auto Thumbnail", f"userset {user_id} tog AUTO_THUMBNAIL t"
            )
            auto_thumb = "Disabled"
        # TMDB Enabled Toggle
        if (
            user_dict.get("TMDB_ENABLED", False)
            or "TMDB_ENABLED" not in user_dict
            and Config.TMDB_ENABLED
        ):
            buttons.data_button(
                "✘ TMDB Enabled", f"userset {user_id} tog TMDB_ENABLED f"
            )
            tmdb_enabled = "Yes"
        else:
            buttons.data_button(
                "✓ TMDB Enabled", f"userset {user_id} tog TMDB_ENABLED t"
            )
            tmdb_enabled = "No"
        # IMDB Enabled Toggle
        if (
            user_dict.get("IMDB_ENABLED", False)
            or "IMDB_ENABLED" not in user_dict
            and Config.IMDB_ENABLED
        ):
            buttons.data_button(
                "✘ IMDB Enabled", f"userset {user_id} tog IMDB_ENABLED f"
            )
            imdb_enabled = "Yes"
        else:
            buttons.data_button(
                "✓ IMDB Enabled", f"userset {user_id} tog IMDB_ENABLED t"
            )
            imdb_enabled = "No"
        # TMDB Adult Content Toggle
        if (
            user_dict.get("TMDB_ADULT_CONTENT", False)
            or "TMDB_ADULT_CONTENT" not in user_dict
            and Config.TMDB_ADULT_CONTENT
        ):
            buttons.data_button(
                "✘ Adult Content", f"userset {user_id} tog TMDB_ADULT_CONTENT f"
            )
            tmdb_adult = "Allowed"
        else:
            buttons.data_button(
                "✓ Adult Content", f"userset {user_id} tog TMDB_ADULT_CONTENT t"
            )
            tmdb_adult = "Blocked"
        buttons.data_button("TMDB API Key", f"userset {user_id} menu TMDB_API_KEY")
        tmdb_api_key = user_dict.get("TMDB_API_KEY", Config.TMDB_API_KEY) or "Not Set"
        buttons.data_button("TMDB Language", f"userset {user_id} menu TMDB_LANGUAGE")
        tmdb_language = user_dict.get("TMDB_LANGUAGE", Config.TMDB_LANGUAGE) or "en-US"
        buttons.data_button("❰", f"userset {user_id} thumb_options", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        btns = buttons.build_menu(2)
        text = f"""⌬ <b>TMDB Settings :</b>
╭ <b>Name</b> → {user_name}
┊ Auto Thumbnail → <b>{auto_thumb}</b>
┊ TMDB Enabled → <b>{tmdb_enabled}</b>
┊ IMDB Enabled → <b>{imdb_enabled}</b>
┊ Adult Content → <b>{tmdb_adult}</b>
┊ TMDB API Key → <b>{tmdb_api_key}</b>
╰ TMDB Language → <b>{tmdb_language}</b>
"""
    elif stype == "rclone":
        buttons.data_button("Rclone Config", f"userset {user_id} menu RCLONE_CONFIG")
        buttons.data_button(
            "Default Rclone Path", f"userset {user_id} menu RCLONE_PATH"
        )
        buttons.data_button("Rclone Flags", f"userset {user_id} menu RCLONE_FLAGS")
        buttons.data_button("❰", f"userset {user_id} back mirror", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        rccmsg = "Exists" if await aiopath.exists(rclone_conf) else "Not Exists"
        if user_dict.get("RCLONE_PATH", False):
            rccpath = user_dict["RCLONE_PATH"]
        elif Config.RCLONE_PATH:
            rccpath = Config.RCLONE_PATH
        else:
            rccpath = "None"
        btns = buttons.build_menu(1)
        if user_dict.get("RCLONE_FLAGS", False):
            rcflags = user_dict["RCLONE_FLAGS"]
        elif "RCLONE_FLAGS" not in user_dict and Config.RCLONE_FLAGS:
            rcflags = Config.RCLONE_FLAGS
        else:
            rcflags = "None"
        text = f"""⌬ <b>RClone Settings :</b>
╭ <b>Name</b> → {user_name}
┊ <b>Rclone Config</b> → <b>{rccmsg}</b>
┊ <b>Rclone Flags</b> → <code>{rcflags}</code>
╰ <b>Rclone Path</b> → <code>{rccpath}</code>
"""
    elif stype == "gdrive":
        buttons.data_button("token.pickle", f"userset {user_id} menu TOKEN_PICKLE")
        buttons.data_button("Default Gdrive ID", f"userset {user_id} menu GDRIVE_ID")
        buttons.data_button("Index URL", f"userset {user_id} menu INDEX_URL")
        if (
            user_dict.get("STOP_DUPLICATE", False)
            or "STOP_DUPLICATE" not in user_dict
            and Config.STOP_DUPLICATE
        ):
            buttons.data_button(
                "Disable Stop Duplicate", f"userset {user_id} tog STOP_DUPLICATE f"
            )
            sd_msg = "Enabled"
        else:
            buttons.data_button(
                "Enable Stop Duplicate",
                f"userset {user_id} tog STOP_DUPLICATE t",
                "l_body",
            )
            sd_msg = "Disabled"
        buttons.data_button("❰", f"userset {user_id} back mirror", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        tokenmsg = "Exists" if await aiopath.exists(token_pickle) else "Not Exists"
        if user_dict.get("GDRIVE_ID", False):
            gdrive_id = user_dict["GDRIVE_ID"]
        elif GDID := Config.GDRIVE_ID:
            gdrive_id = GDID
        else:
            gdrive_id = "None"
        index = user_dict["INDEX_URL"] if user_dict.get("INDEX_URL", False) else "None"
        btns = buttons.build_menu(2)
        text = f"""⌬ <b>GDrive Tools Settings :</b>
╭ <b>Name</b> → {user_name}
┊ <b>Gdrive Token</b> → <b>{tokenmsg}</b>
┊ <b>Gdrive ID</b> → <code>{gdrive_id}</code>
┊ <b>Index URL</b> → <code>{index}</code>
╰ <b>Stop Duplicate</b> → <b>{sd_msg}</b>
"""
    elif stype == "mirror":
        buttons.data_button("RClone Tools", f"userset {user_id} rclone")
        rccmsg = "Exists" if await aiopath.exists(rclone_conf) else "Not Exists"
        if user_dict.get("RCLONE_PATH", False):
            rccpath = user_dict["RCLONE_PATH"]
        elif RP := Config.RCLONE_PATH:
            rccpath = RP
        else:
            rccpath = "None"

        buttons.data_button("GDrive Tools", f"userset {user_id} gdrive")
        tokenmsg = "Exists" if await aiopath.exists(token_pickle) else "Not Exists"
        if user_dict.get("GDRIVE_ID", False):
            gdrive_id = user_dict["GDRIVE_ID"]
        elif GI := Config.GDRIVE_ID:
            gdrive_id = GI
        else:
            gdrive_id = "None"
        index = user_dict["INDEX_URL"] if user_dict.get("INDEX_URL", False) else "None"

        if (
            user_dict.get("STOP_DUPLICATE", False)
            or "STOP_DUPLICATE" not in user_dict
            and Config.STOP_DUPLICATE
        ):
            sd_msg = "Enabled"
        else:
            sd_msg = "Disabled"

        buttons.data_button("❰", f"userset {user_id} back", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")

        btns = buttons.build_menu(1)
        text = f"""⌬ <b>Mirror Settings :</b>
╭ <b>Name</b> → {user_name}
┊ <b>Rclone Config</b> → <b>{rccmsg}</b>
┊ <b>Rclone Path</b> → <code>{rccpath}</code>
┊ <b>Gdrive Token</b> → <b>{tokenmsg}</b>
┊ <b>Gdrive ID</b> → <code>{gdrive_id}</code>
┊ <b>Index Link</b> → <code>{index}</code>
╰ <b>Stop Duplicate</b> → <b>{sd_msg}</b>
"""
    elif stype == "ffset":
        buttons.data_button("FFmpeg Cmds", f"userset {user_id} menu FFMPEG_CMDS")
        if user_dict.get("FFMPEG_CMDS", False):
            ffc = user_dict["FFMPEG_CMDS"]
        elif "FFMPEG_CMDS" not in user_dict and Config.FFMPEG_CMDS:
            ffc = Config.FFMPEG_CMDS
        else:
            ffc = "<b>Not Exists</b>"
        if isinstance(ffc, dict):
            ffc = "\n" + "\n".join(
                [
                    f"{no}. <b>{key}</b>: <code>{value[0]}</code>"
                    for no, (key, value) in enumerate(ffc.items(), start=1)
                ]
            )

        buttons.data_button("❰", f"userset {user_id} back", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")

        btns = buttons.build_menu(2)
        text = f"""⌬ <b>FF Settings :</b>
╭ <b>Name</b> → {user_name}
╰ <b>FFmpeg Commands</b> → {ffc}"""

    elif stype == "auto_process":
        # Auto Leech/Mirror/YT Leech settings
        auto_yt_leech = user_dict.get("AUTO_YT_LEECH", False)
        auto_leech = user_dict.get("AUTO_LEECH", False)
        auto_mirror = user_dict.get("AUTO_MIRROR", False)
        
        if auto_yt_leech:
            buttons.data_button(
                "✘ Auto YT Leech",
                f"userset {user_id} tog AUTO_YT_LEECH f",
            )
            ayt_status = "Enabled"
        else:
            buttons.data_button(
                "✓ Auto YT Leech",
                f"userset {user_id} tog AUTO_YT_LEECH t",
            )
            ayt_status = "Disabled"
        
        if auto_leech:
            buttons.data_button(
                "✘ Auto Leech",
                f"userset {user_id} tog AUTO_LEECH f",
            )
            al_status = "Enabled"
        else:
            buttons.data_button(
                "✓ Auto Leech",
                f"userset {user_id} tog AUTO_LEECH t",
            )
            al_status = "Disabled"
        
        if auto_mirror:
            buttons.data_button(
                "✘ Auto Mirror",
                f"userset {user_id} tog AUTO_MIRROR f",
            )
            am_status = "Enabled"
        else:
            buttons.data_button(
                "✓ Auto Mirror",
                f"userset {user_id} tog AUTO_MIRROR t",
            )
            am_status = "Disabled"
        
        buttons.data_button("❰", f"userset {user_id} back")
        buttons.data_button("✘", f"userset {user_id} close")
        
        btns = buttons.build_menu(2)
        text = f"""<u>Auto Processing Settings for {user_name}</u>

<b>Auto YT Leech:</b> {ayt_status}
<b>Auto Leech:</b> {al_status}
<b>Auto Mirror:</b> {am_status}

<i> Auto YT Leech: Automatically leech YouTube/video URLs only
 Auto Leech: Automatically leech ALL content (URLs + media)
 Auto Mirror: Automatically mirror ALL content (URLs + media)

Priority: AUTO_YT_LEECH > AUTO_LEECH > AUTO_MIRROR
If only Auto YT Leech is enabled, only video URLs are processed.</i>"""
    elif stype == "auto_rename":
        # Auto Rename settings
        auto_rename = user_dict.get("AUTO_RENAME", False)
        rename_template = user_dict.get(
            "RENAME_TEMPLATE", "S{season}E{episode}Q{quality}"
        )
        start_episode = user_dict.get("START_EPISODE", 1)
        start_season = user_dict.get("START_SEASON", 1)

        if auto_rename:
            buttons.data_button(
                "✘ Auto Rename",
                f"userset {user_id} tog AUTO_RENAME f",
            )
            ar_status = "Enabled"
        else:
            buttons.data_button(
                "✓ Auto Rename",
                f"userset {user_id} tog AUTO_RENAME t",
            )
            ar_status = "Disabled"

        buttons.data_button(
            "Set Template",
            f"userset {user_id} menu RENAME_TEMPLATE",
        )
        buttons.data_button(
            "Set Start Episode",
            f"userset {user_id} menu START_EPISODE",
        )
        buttons.data_button(
            "Set Start Season",
            f"userset {user_id} menu START_SEASON",
        )
        buttons.data_button("❰", f"userset {user_id} back")
        buttons.data_button("✘", f"userset {user_id} close")

        btns = buttons.build_menu(2)
        text = f"""<u>Auto Rename Settings for {user_name}</u>

<b>Status:</b> {ar_status}
<b>Template:</b> <code>{rename_template}</code>
<b>Start Episode:</b> {start_episode}
<b>Start Season:</b> {start_season}

<b><u>Template Variables (IMDB Integrated):</u></b>
• <code>{{season}}</code> - Season number
• <code>{{episode}}</code> - Episode (padded: 01, 02)
• <code>{{episode2}}</code> - Episode (unpadded: 1, 2)
• <code>{{quality}}</code> - Video quality (720, 1080)
• <code>{{audio}}</code> - Audio language or MultiAuD
• <code>{{title}}</code> - IMDB title
• <code>{{year}}</code> - Release year
• <code>{{rating}}</code> - IMDB rating
• <code>{{genre}}</code> - Genre(s)

<b>Examples:</b>
<code>S{{season}}E{{episode}}Q{{quality}}</code>
<code>{{title}} ({{year}}) S{{season}}E{{episode}} [{{quality}}p]</code>
<code>{{title}}.{{year}}.S{{season}}E{{episode}}.{{quality}}p.{{audio}}</code>

<i>Auto Rename works for both Leech and Mirror operations.
Automatically fetches IMDB info and renames files using the template.</i>
"""
    elif stype == "advanced":
        buttons.data_button(
            "Excluded Extensions", f"userset {user_id} menu EXCLUDED_EXTENSIONS"
        )
        if user_dict.get("EXCLUDED_EXTENSIONS", False):
            ex_ex = user_dict["EXCLUDED_EXTENSIONS"]
        elif "EXCLUDED_EXTENSIONS" not in user_dict:
            ex_ex = excluded_extensions
        else:
            ex_ex = "None"
        if ex_ex != "None":
            ex_ex = ", ".join(ex_ex)

        ns_msg = (
            f"<code>{swap}</code>"
            if (swap := user_dict.get("NAME_SWAP", False))
            else "<b>Not Exists</b>"
        )
        buttons.data_button("Name Swap", f"userset {user_id} menu NAME_SWAP")

        buttons.data_button("YT-DLP Options", f"userset {user_id} menu YT_DLP_OPTIONS")
        if user_dict.get("YT_DLP_OPTIONS", False):
            ytopt = user_dict["YT_DLP_OPTIONS"]
        elif "YT_DLP_OPTIONS" not in user_dict and Config.YT_DLP_OPTIONS:
            ytopt = Config.YT_DLP_OPTIONS
        else:
            ytopt = "None"
        upload_paths = user_dict.get("UPLOAD_PATHS", {})
        if not upload_paths and "UPLOAD_PATHS" not in user_dict and Config.UPLOAD_PATHS:
            upload_paths = Config.UPLOAD_PATHS
        else:
            upload_paths = "None"
        buttons.data_button("Upload Paths", f"userset {user_id} menu UPLOAD_PATHS")
        yt_cookie_path = f"cookies/{user_id}.txt"
        user_cookie_msg = (
            "Exists" if await aiopath.exists(yt_cookie_path) else "Not Exists"
        )
        buttons.data_button(
            "YT Cookie File", f"userset {user_id} menu USER_COOKIE_FILE"
        )
        buttons.data_button("❰", f"userset {user_id} back", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        btns = buttons.build_menu(1)
        text = f"""⌬ <b>Advanced Settings :</b>
╭ <b>Name</b> → {user_name}
┊ <b>Name Swaps</b> → {ns_msg}
┊ <b>Excluded Extensions</b> → <code>{ex_ex}</code>
┊ <b>Upload Paths</b> → <b>{upload_paths}</b>
┊ <b>YT-DLP Options</b> → <code>{ytopt}</code>
╰ <b>YT User Cookie File</b> → <b>{user_cookie_msg}</b>
"""
    return text, btns, thumbnail

async def update_user_settings(query, stype="main"):
    handler_dict[query.from_user.id] = False
    msg, button, thumbnail = await get_user_settings(query.from_user, stype)
    await edit_message(query.message, msg, button)

@new_task
async def send_user_settings(_, message):
    from_user = message.from_user
    handler_dict[from_user.id] = False
    msg, button, thumbnail = await get_user_settings(from_user)
    await send_message(message, msg, button, photo=thumbnail)

@new_task
async def add_file(_, message, ftype, rfunc):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    if ftype == "THUMBNAIL":
        des_dir = await create_thumb(message, user_id)
    elif ftype == "RCLONE_CONFIG":
        rpath = f"{getcwd()}/rclone/"
        await makedirs(rpath, exist_ok=True)
        des_dir = f"{rpath}{user_id}.conf"
        await message.download(file_name=des_dir)
    elif ftype == "TOKEN_PICKLE":
        tpath = f"{getcwd()}/tokens/"
        await makedirs(tpath, exist_ok=True)
        des_dir = f"{tpath}{user_id}.pickle"
        await message.download(file_name=des_dir)
    elif ftype == "USER_COOKIE_FILE":
        cpath = f"{getcwd()}/cookies/{user_id}"
        await makedirs(cpath, exist_ok=True)
        des_dir = f"{cpath}/cookies.txt"
        await message.download(file_name=des_dir)
    await delete_message(message)
    update_user_ldata(user_id, ftype, des_dir)
    await rfunc()
    await database.update_user_doc(user_id, ftype, des_dir)

@new_task
async def add_one(_, message, option, rfunc):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})
    value = message.text
    if value.startswith("{") and value.endswith("}"):
        try:
            value = eval(value)
            if user_dict[option]:
                user_dict[option].update(value)
            else:
                update_user_ldata(user_id, option, value)
        except Exception as e:
            await send_message(message, str(e))
            return
    else:
        await send_message(message, "It must be Dict!")
        return
    await delete_message(message)
    await rfunc()
    await database.update_user_data(user_id)

@new_task
async def remove_one(_, message, option, rfunc):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})
    names = message.text.split("/")
    for name in names:
        if name in user_dict[option]:
            del user_dict[option][name]
    await delete_message(message)
    await rfunc()
    await database.update_user_data(user_id)

@new_task
async def set_option(_, message, option, rfunc):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    if option == "LEECH_SPLIT_SIZE":
        if not value.isdigit():
            value = get_size_bytes(value)
        value = min(int(value), TgClient.MAX_SPLIT_SIZE)
    # elif option == "LEECH_DUMP_CHAT": # TODO: Add logic if needed, e.g., parsing chat ID/username
    elif option == "EXCLUDED_EXTENSIONS":
        fx = value.split()
        value = ["aria2", "!qB"] # Default values
        for x in fx:
            x = x.lstrip(".") # Remove leading dot
            value.append(x.strip().lower()) # Normalize and add
    elif option in ["THUMBNAIL_LAYOUT", "GRID_THUMBNAIL_LAYOUT"]:
        # Validate layout format (e.g., "2x3", "3x3")
        if not re_match(r"^\d+x\d+$", value):
            await send_message(message, "Invalid format! Use format like: 2x3, 3x3, 3x2")
            return
    elif option in ["UPLOAD_PATHS", "FFMPEG_CMDS", "YT_DLP_OPTIONS"]:
        if value.startswith("{") and value.endswith("}"):
            try:
                value = eval(sub(r"\s+", " ", value))
            except Exception as e:
                await send_message(message, str(e))
                return
    elif option in ["START_EPISODE", "START_SEASON"]:
        if not value.isdigit():
            await send_message(message, f"{option} must be a positive number!")
            return
        value = int(value)
        if value < 1:
            await send_message(message, f"{option} must be at least 1!")
            return
    elif option in ["TMDB_API_KEY", "TMDB_LANGUAGE"]:
        pass
    elif option == "RENAME_TEMPLATE":
        template_vars = [
            "{name}",
            "{year}",
            "{quality}",
            "{season}",
            "{episode}",
            "{audio}",
        ]
        has_var = any(var in value for var in template_vars)
        if not has_var:
            await send_message(
                message,
                f"RENAME_TEMPLATE must contain at least one variable: {', '.join(template_vars)}",
            )
            return 
    elif option == "AUTO_RENAME":
        if value not in ["True", "False"]:
            await send_message(message, "AUTO_RENAME must be True or False!")
            return
        value = value == "True"           
    else:
        await send_message(message, "It must be dict!")
        return
    update_user_ldata(user_id, option, value)
    await delete_message(message)
    await rfunc()
    await database.update_user_data(user_id)

async def get_menu(option, message, user_id):
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})
    file_dict = {
        "THUMBNAIL": f"thumbnails/{user_id}.jpg",
        "RCLONE_CONFIG": f"rclone/{user_id}.conf",
        "TOKEN_PICKLE": f"tokens/{user_id}.pickle",
        "USER_COOKIE_FILE": f"cookies/{user_id}/cookies.txt",
    }
    buttons = ButtonMaker()

    if option in ["THUMBNAIL", "RCLONE_CONFIG", "TOKEN_PICKLE", "USER_COOKIE_FILE"]:
        key = "file"
    else:
        key = "set"

    buttons.data_button(
        "Change" if user_dict.get(option, False) else "Set",
        f"userset {user_id} {key} {option}",
    )

    if user_dict.get(option, False):
        if option == "THUMBNAIL":
            buttons.data_button(
                "View Thumb", f"userset {user_id} view THUMBNAIL", "header"
            )
        elif option in ["YT_DLP_OPTIONS", "FFMPEG_CMDS", "UPLOAD_PATHS"]:
            buttons.data_button(
                "Add One", f"userset {user_id} addone {option}", "header"
            )
            buttons.data_button(
                "Remove One", f"userset {user_id} rmone {option}", "header"
            )
        if key != "file":  # TODO: option default val check - Consider removing if always true for non-file options
            buttons.data_button("Reset", f"userset {user_id} reset {option}")
    elif await aiopath.exists(file_dict.get(option, "")): # Use get with default empty string
        buttons.data_button("Remove", f"userset {user_id} remove {option}")

    if option in leech_options:
        back_to = "leech"
    elif option in thumb_options:
        back_to = "thumb_options"
    elif option in rclone_options:
        back_to = "rclone"
    elif option in gdrive_options:
        back_to = "gdrive"
    elif option in ffset_options:
        back_to = "ffset"
    elif option in advanced_options:
        back_to = "advanced"
    elif option in rename_options:
        back_to = "auto_rename"
    elif option in tmdb_options:
        back_to = "tmdb"        
    else:
        back_to = "back"

    buttons.data_button("❰", f"userset {user_id} {back_to}", "footer")
    buttons.data_button("✘", f"userset {user_id} close", "footer")

    val = user_dict.get(option)
    if option in file_dict and await aiopath.exists(file_dict[option]):
        val = "<b>Exists</b>"
    elif option == "LEECH_SPLIT_SIZE":
        val = get_readable_file_size(val)
    # Safely get description texts, defaulting to generic messages if key is missing
    desc_tuple = user_settings_text.get(option, ("", "", ""))
    text = f"""⌬ <b><u>Menu Settings :</u></b>
╭ <b>Option</b> → {option}
┊ <b>Option's Value</b> → {val if val else "<b>Not Exists</b>"}
┊ <b>Default Input Type</b> → {desc_tuple[0] if desc_tuple[0] else "Text/Dict/File"}
╰ <b>Description</b> → {desc_tuple[1] if desc_tuple[1] else "Set the value for this option."}
"""
    await edit_message(message, text, buttons.build_menu(2))

async def event_handler(client, query, pfunc, rfunc, photo=False, document=False):
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = update_time = time()

    async def event_filter(_, __, event):
        if photo:
            mtype = event.photo or event.document # Accept photo or doc for thumbnail
        elif document:
            mtype = event.document
        else:
            mtype = event.text
        user = event.from_user or event.sender_chat
        return bool(
            user.id == user_id and event.chat.id == query.message.chat.id and mtype
        )
    handler = client.add_handler(
        MessageHandler(pfunc, filters=create(event_filter)), group=-1
    )
    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await rfunc()
        elif time() - update_time > 8 and handler_dict[user_id]:
            update_time = time()
            msg = await client.get_messages(query.message.chat.id, query.message.id)
            text = msg.text.split("\n")
            text[-1] = (
                f"╰ <b>Time Left :</b> <code>{round(60 - (time() - start_time), 2)} sec</code>"
            )
            await edit_message(msg, "\n".join(text), msg.reply_markup)
    client.remove_handler(*handler)

@new_task
async def edit_user_settings(client, query):
    from_user = query.from_user
    user_id = from_user.id
    name = from_user.mention
    message = query.message
    data = query.data.split()
    handler_dict[user_id] = False
    thumb_path = f"thumbnails/{user_id}.jpg"
    rclone_conf = f"rclone/{user_id}.conf"
    token_pickle = f"tokens/{user_id}.pickle"
    yt_cookie_path = f"cookies/{user_id}/cookies.txt"
    user_dict = user_data.get(user_id, {})

    if user_id != int(data[1]):
        return await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "setevent":
        await query.answer()
    elif data[2] in [
        "general",
        "mirror",
        "leech",
        "ffset",
        "advanced",
        "gdrive",
        "rclone",
        "thumb_options",
        "auto_process",
        "auto_rename",
        "tmdb",
    ]:
        await query.answer()
        await update_user_settings(query, data[2])
    elif data[2] == "menu":
        await query.answer()
        await get_menu(data[3], message, user_id)
    elif data[2] == "tog":
        await query.answer()
        update_user_ldata(user_id, data[3], data[4] == "t")
        if data[3] == "STOP_DUPLICATE":
            back_to = "gdrive"
        elif data[3] in ["USER_TOKENS", "USE_USER_COOKIE"]:
            back_to = "general"
        elif data[3] == "USE_GRID_THUMBNAIL":  # NEW
            back_to = "thumb_options"
        elif data[3] == "AUTO_PROCESS":
            back_to = "auto_process"
        elif data[3] == "AUTO_RENAME":
            back_to = "auto_rename"
        elif data[3] in tmdb_options:
            back_to = "tmdb"
        else:
            back_to = "leech"
        await update_user_settings(query, stype=back_to)
        await database.update_user_data(user_id)
    elif data[2] == "file":
        await query.answer()
        buttons = ButtonMaker()
        # Safely get the instruction text, defaulting if key is missing
        text_desc = user_settings_text.get(data[3], ("", "", "<i>No instructions available.</i>\n" "╰ <b>Time Left :</b> <code>60 sec</code>"))[2]
        buttons.data_button("⬢", f"userset {user_id} menu {data[3]} stop")
        buttons.data_button("❰", f"userset {user_id} menu {data[3]}", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        await edit_message(
            message, message.text.html + "\n" + text_desc, buttons.build_menu(1)
        )
        rfunc = partial(get_menu, data[3], message, user_id)
        pfunc = partial(add_file, ftype=data[3], rfunc=rfunc)
        await event_handler(
            client,
            query,
            pfunc,
            rfunc,
            photo=data[3] == "THUMBNAIL",
            document=data[3] != "THUMBNAIL",
        )
    elif data[2] in ["set", "addone", "rmone"]:
        await query.answer()
        buttons = ButtonMaker()
        if data[2] == "set":
            # Safely get the instruction text
            text_desc = user_settings_text.get(data[3], ("", "", "<i>No instructions available.</i>\n" "╰ <b>Time Left :</b> <code>60 sec</code>"))[2]
            func = set_option
        elif data[2] == "addone":
            text_desc = f"Add one or more string key and value to {data[3]}. Example: {{'key 1': 62625261, 'key 2': 'value 2'}}. Timeout: 60 sec"
            func = add_one
        elif data[2] == "rmone":
            text_desc = f"Remove one or more key from {data[3]}. Example: key 1/key2/key 3. Timeout: 60 sec"
            func = remove_one
        buttons.data_button("⬢", f"userset {user_id} menu {data[3]} stop")
        buttons.data_button("❰", f"userset {user_id} menu {data[3]}", "footer")
        buttons.data_button("✘", f"userset {user_id} close", "footer")
        await edit_message(
            message, message.text.html + "\n" + text_desc, buttons.build_menu(1)
        )
        rfunc = partial(get_menu, data[3], message, user_id)
        pfunc = partial(func, option=data[3], rfunc=rfunc)
        await event_handler(client, query, pfunc, rfunc)
    elif data[2] == "remove":
        await query.answer("Removed!", show_alert=True)
        if data[3] in ["THUMBNAIL", "RCLONE_CONFIG", "TOKEN_PICKLE", "USER_COOKIE_FILE"]:
            if data[3] == "THUMBNAIL":
                fpath = thumb_path
            elif data[3] == "RCLONE_CONFIG":
                fpath = rclone_conf
            elif data[3] == "USER_COOKIE_FILE":
                fpath = yt_cookie_path
            else:
                fpath = token_pickle
            if await aiopath.exists(fpath):
                await remove(fpath)
            # Only remove from user_dict if key exists there
            if data[3] in user_dict:
                 del user_dict[data[3]]
            await database.update_user_doc(user_id, data[3])
        else:
            update_user_ldata(user_id, data[3], "")
            await database.update_user_data(user_id)
        await get_menu(data[3], message, user_id)
    elif data[2] == "reset":
        await query.answer("Reset Done!", show_alert=True)
        if data[3] in user_dict:
            del user_dict[data[3]]
        await get_menu(data[3], message, user_id)
    elif data[2] == "resetall": # Added for completeness if 'reset all' button uses this handler
         await query.answer("Reset All Done!", show_alert=True)
         for k in list(user_dict.keys()):
             if k not in ("SUDO", "AUTH", "VERIFY_TOKEN", "VERIFY_TIME"): # Exclude critical keys
                 del user_dict[k]
         for fpath in [thumb_path, rclone_conf, token_pickle, yt_cookie_path]:
             if await aiopath.exists(fpath):
                 await remove(fpath)
         await update_user_settings(query)
         await database.update_user_data(user_id)
    elif data[2] == "view":
        await query.answer()
        await send_file(message, thumb_path, name)
    elif data[2] in ["gd", "rc"]:
        await query.answer()
        du = "rc" if data[2] == "gd" else "gd"
        update_user_ldata(user_id, "DEFAULT_UPLOAD", du)
        await update_user_settings(query, stype="general")
        await database.update_user_data(user_id)
    elif data[2] == "back":
        await query.answer()
        stype = data[3] if len(data) == 4 else "main"
        await update_user_settings(query, stype)
    else:
        await query.answer()
        await delete_message(message, message.reply_to_message)

@new_task
async def get_users_settings(_, message):
    msg = ""
    if auth_chats:
        msg += f"AUTHORIZED_CHATS: {auth_chats}\n"
    if sudo_users:
        msg += f"SUDO_USERS: {sudo_users}\n"
    if user_data:
        for u, d in user_data.items():
            kmsg = f"\n<b>{u}:</b>\n"
            if vmsg := "".join(
                f"{k}: <code>{v or None}</code>\n" for k, v in d.items()
            ):
                msg += kmsg + vmsg
    if not msg:
        await send_message(message, "No users data!")
        return
    msg_ecd = msg.encode()
    if len(msg_ecd) > 4000:
        with BytesIO(msg_ecd) as ofile:
            ofile.name = "users_settings.txt"
            await send_file(message, ofile)
    else:
        await send_message(message, msg)
