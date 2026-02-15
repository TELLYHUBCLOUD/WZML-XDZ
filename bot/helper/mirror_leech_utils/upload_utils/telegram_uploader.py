from asyncio import sleep
from logging import getLogger
from os import path as ospath, walk
from re import match as re_match, sub as re_sub
from time import time

from aioshutil import rmtree
from natsort import natsorted
from PIL import Image
from pyrogram.errors import BadRequest, FloodWait, RPCError
from bot.helper.telly_utils.auto_thumbnail import AutoThumbnailHelper

try:
    from pyrogram.errors import FloodPremiumWait
except ImportError:
    FloodPremiumWait = FloodWait
from aiofiles.os import (
    path as aiopath,
    remove,
    rename,
)
from pyrogram.types import (
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
)
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ....core.config_manager import Config
from ....core.tg_client import TgClient
from .... import user_data
from ...ext_utils.bot_utils import sync_to_async
from ...ext_utils.files_utils import get_base_name, is_archive
from ...ext_utils.status_utils import get_readable_file_size, get_readable_time
from ...ext_utils.media_utils import (
    get_audio_thumbnail,
    get_document_type,
    get_media_info,
    get_multiple_frames_thumbnail,
    get_video_thumbnail,
    get_md5_hash,
)
from ...telegram_helper.message_utils import delete_message

LOGGER = getLogger(__name__)


class TelegramUploader:
    def __init__(self, listener, path):
        self._last_uploaded = 0
        self._processed_bytes = 0
        self._listener = listener
        self._path = path
        self._client = None
        self._start_time = time()
        self._total_files = 0
        self._thumb = self._listener.thumb or f"thumbnails/{listener.user_id}.jpg"
        self._msgs_dict = {}
        self._corrupted = 0
        self._is_corrupted = False
        self._media_dict = {"videos": {}, "documents": {}}
        self._last_msg_in_group = False
        self._up_path = ""
        self._lprefix = ""
        self._lsuffix = ""
        self._lcaption = ""
        self._lfont = ""
        self._bot_pm = False
        self._media_group = False
        self._is_private = False
        self._sent_msg = None
        self._log_msg = None
        self._user_session = self._listener.user_transmission
        self._error = ""
        self._use_grid_thumb = False  # NEW
        self._grid_layout = "2x3"  # NEW

    async def _upload_progress(self, current, _):
        if self._listener.is_cancelled:
            if self._user_session:
                TgClient.user.stop_transmission()
            else:
                self._listener.client.stop_transmission()
        chunk_size = current - self._last_uploaded
        self._last_uploaded = current
        self._processed_bytes += chunk_size

    async def _user_settings(self):
        settings_map = {
            "MEDIA_GROUP": ("_media_group", False),
            "BOT_PM": ("_bot_pm", False),
            "LEECH_PREFIX": ("_lprefix", ""),
            "LEECH_SUFFIX": ("_lsuffix", ""),
            "LEECH_CAPTION": ("_lcaption", ""),
            "LEECH_FONT": ("_lfont", ""),
            "USE_GRID_THUMBNAIL": ("_use_grid_thumb", False),  # NEW
            "GRID_THUMBNAIL_LAYOUT": ("_grid_layout", "2x3"),  # NEW
        }

        for key, (attr, default) in settings_map.items():
            setattr(
                self,
                attr,
                self._listener.user_dict.get(key) or getattr(Config, key, default),
            )

        if self._thumb != "none" and not await aiopath.exists(self._thumb):
            self._thumb = None
    async def _get_original_filename_for_thumbnail(self, filename):
        """
        Get the original filename for auto thumbnail generation.
        For split files (e.g., movie.mkv.001, movie.mkv.002), returns the original filename (movie.mkv).
        For regular files, returns the filename as-is.
        """

        # Check for split file patterns
        # Pattern 1: filename.ext.001, filename.ext.002, etc.
        match = re_match(r"(.+\.\w+)\.(\d{3})$", filename)
        if match:
            return match.group(1)  # Return filename.ext without the .001 part

        # Pattern 2: filename.part001.ext, filename.part002.ext, etc.
        match = re_match(r"(.+)\.part\d+(\.\w+)$", filename)
        if match:
            return f"{match.group(1)}{match.group(2)}"  # Return filename.ext without the .part001 part

        # Pattern 3: filename.001, filename.002 (no extension before split number)
        match = re_match(r"(.+)\.(\d{3})$", filename)
        if match:
            # This is trickier - we need to guess the original extension
            # For now, return the base name and let the auto thumbnail helper handle it
            return match.group(1)

        # Not a split file, return as-is
        return filename
    async def _msg_to_reply(self):
        if self._listener.up_dest:
            msg_link = (
                self._listener.message.link if self._listener.is_super_chat else ""
            )
            msg = f"""➲ <b><u>Leech Started :</u></b>
┃
┊ <b>User :</b> {self._listener.user.mention} ( #ID{self._listener.user_id} ){f"\n┊ <b>Message Link :</b> <a href='{msg_link}'>Click Here</a>" if msg_link else ""}
╰ <b>Source :</b> <a href='{self._listener.source_url}'>Click Here</a>"""
            try:
                self._log_msg = await TgClient.bot.send_message(
                    chat_id=self._listener.up_dest,
                    text=msg,
                    disable_web_page_preview=True,
                    message_thread_id=self._listener.chat_thread_id,
                    disable_notification=True,
                )
                self._sent_msg = self._log_msg
                if self._user_session:
                    self._sent_msg = await TgClient.user.get_messages(
                        chat_id=self._sent_msg.chat.id,
                        message_ids=self._sent_msg.id,
                    )
                else:
                    self._is_private = self._sent_msg.chat.type.name == "PRIVATE"
            except Exception as e:
                await self._listener.on_upload_error(str(e))
                return False

        elif self._user_session:
            self._sent_msg = await TgClient.user.get_messages(
                chat_id=self._listener.message.chat.id, message_ids=self._listener.mid
            )
            if self._sent_msg is None:
                self._sent_msg = await TgClient.user.send_message(
                    chat_id=self._listener.message.chat.id,
                    text="Deleted Cmd Message! Don't delete the cmd message again!",
                    disable_web_page_preview=True,
                    disable_notification=True,
                )
        else:
            self._sent_msg = self._listener.message
        return True

    async def _prepare_file(self, file_, dirpath):
        # --- AUTO RENAME LOGIC ---
        import re  # Import re module for both auto-rename logic and clean_filename_for_title function
        import json
        import subprocess
        
        user_dict = getattr(self._listener, 'user_dict', {})
        auto_rename = user_dict.get('AUTO_RENAME', False)
        pre_file_ = file_  # Store original filename
        
        if auto_rename:
            try:
                template = user_dict.get('RENAME_TEMPLATE', 'S{season}E{episode}Q{quality}')
                episode = int(user_dict.get('_CURRENT_EPISODE', user_dict.get('START_EPISODE', 1)))
                season = int(user_dict.get('START_SEASON', 1))
                
                up_path = ospath.join(dirpath, pre_file_)
                _, quality, lang, _ = await get_media_info(up_path, True)
                quality = str(quality).replace('p', '') if quality else ''

                # Clean filename to get probable title
                def clean_filename_for_title(filename):
                    # Use extract_media_info to get the best title and year
                    name, _season, _episode, year, part, volume = extract_media_info(filename)
                    # If we have both name and year, return 'Name Year'
                    if name and year:
                        result = f"{name} {year}"
                    elif name:
                        result = name
                    else:
                        # fallback to old logic if extract_media_info fails
                        name = ospath.splitext(filename)[0]
                        name = re.sub(r'[\[\](){}⟨⟩【】『』""''«»‹›❮❯❰❱❲❳❴❵]', ' ', name)
                        name = re.sub(r'\s+', ' ', name).strip()
                        result = name if name else 'Unknown'
                    LOGGER.info(f"Final cleaned title for lookups: '{result}'")
                    return result
                    
                probable_title = clean_filename_for_title(pre_file_)
                
                # Fetch IMDB info
                from bot.modules.imdb import get_poster
                imdb_info = None
                if probable_title:
                    imdb_info = get_poster(probable_title)
                if imdb_info:
                    imdb_data = {
                        'title': imdb_info.get('title', ''),
                        'year': imdb_info.get('year', ''),
                        'rating': imdb_info.get('rating', '').replace(' / 10', ''),
                        'genre': imdb_info.get('genres', ''),
                    }
                else:
                    imdb_data = {'title': probable_title, 'year': '', 'rating': '', 'genre': ''}
                    
                # Get audio language(s)
                audio_count = 0
                audio = lang or ''
                try:
                    ffprobe_cmd = [
                        'ffprobe', '-v', 'error', '-select_streams', 'a', 
                        '-show_entries', 'stream=index', '-of', 'json', up_path
                    ]
                    ffprobe_out = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=30)
                    if ffprobe_out.returncode == 0:
                        audio_json = json.loads(ffprobe_out.stdout)
                        audio_count = len(audio_json.get('streams', []))
                    if audio_count >= 2:
                        audio = 'MultiAuD'
                except Exception:
                    pass
                    
                # Merge all fields for template - episode will be updated later
                template_fields = dict(
                    season=season,
                    episode2=episode,  # integer, for E1, E2, ...
                    episode=f"{episode:02d}",  # zero-padded, for E01, E02, ...
                    quality=quality,
                    audio=audio,
                    **imdb_data
                )
                
                # Check if this is a multi-resolution file (contains pattern like _720p_BL, _480p_BL, etc.)
                is_multi_resolution_file = bool(re.search(r'_\d+p_BL\.', pre_file_))
                
                # Handle episode numbering for multi-resolution files
                if is_multi_resolution_file:
                    # Check if we've already processed a file from this batch
                    base_filename = re.sub(r'_\d+p_BL\.', '.', pre_file_)  # Remove quality suffix
                    batch_key = f"multi_res_batch_{base_filename}"
                    
                    # For multi-resolution batch, use the same episode number for all files
                    if not user_dict.get(batch_key, False):
                        # First file in batch - increment and store the episode number
                        user_dict['_CURRENT_EPISODE'] = episode + 1
                        user_dict[batch_key] = episode  # Store the episode number to use for this batch
                        current_episode = episode  # Use original episode for this batch
                        LOGGER.info(f"Multi-resolution batch detected. Episode {episode} will be used for all files in batch: {base_filename}")
                    else:
                        # Subsequent files in batch - use the same episode number as the first file
                        current_episode = user_dict[batch_key]
                        LOGGER.info(f"Multi-resolution file from same batch, using episode {current_episode}: {pre_file_}")
                    
                    # Clean up old batch keys to prevent memory buildup (keep only recent 50 keys)
                    batch_keys = [k for k in user_dict.keys() if k.startswith("multi_res_batch_")]
                    if len(batch_keys) > 50:
                        # Remove oldest batch keys (simple cleanup)
                        for key in sorted(batch_keys)[:-50]:
                            user_dict.pop(key, None)
                            
                    # Update template fields with correct episode
                    template_fields['episode2'] = current_episode
                    template_fields['episode'] = f"{current_episode:02d}"
                else:
                    # Regular single file - increment episode counter normally
                    user_dict['_CURRENT_EPISODE'] = episode + 1
                    LOGGER.info(f"Single file processed. Using episode {episode}, next will be {episode + 1}: {pre_file_}")
                
                # Apply template to generate new filename
                try:
                    new_name = template.format(**template_fields)
                    ext = ospath.splitext(pre_file_)[1]
                    file_ = f"{new_name}{ext}"
                    LOGGER.info(f"Auto renamed for leech: '{pre_file_}' -> '{file_}' (Episode {template_fields['episode2']})")
                except Exception as e:
                    LOGGER.error(f"Failed to apply rename template: {e}")
                    file_ = pre_file_  # Keep original name if template fails
            except Exception as e:
                LOGGER.error(f"Auto rename failed for leech: {e}")
                file_ = pre_file_  # Keep original name if auto rename fails
        
        # Continue with existing logic using file_ (which may be renamed)
        if self._lcaption:
            # Pass media_info to generate_caption if available
            cap_mono = await generate_caption(file_, dirpath, self._lcaption, media_info=media_info if auto_rename else None)
        if self._lprefix:
            if not self._lcaption:
                cap_mono = f"{self._lprefix} {file_}"
            self._lprefix = re_sub("<.*?>", "", self._lprefix)
            new_path = ospath.join(dirpath, f"{self._lprefix} {file_}")
            LOGGER.info(self._up_path)
            await rename(self._up_path, new_path)
            self._up_path = new_path
            LOGGER.info(self._up_path)
        elif auto_rename and file_ != pre_file_:
            # Rename file on disk if auto rename was applied and no prefix
            new_path = ospath.join(dirpath, file_)
            await rename(self._up_path, new_path)
            self._up_path = new_path
            
        if not self._lcaption and not self._lprefix:
            cap_mono = f"<code>{file_}</code>"
        if len(file_) > 60:
            if is_archive(file_):
                name = get_base_name(file_)
                ext = file_.split(name, 1)[1]
            elif match := re_match(
                r".+(?=\..+\.0*\d+$)|.+(?=\.part\d+\..+$)",
                file_,
            ):
                name = match.group(0)
                ext = file_.split(name, 1)[1]
            elif len(fsplit := ospath.splitext(file_)) > 1:
                name = fsplit[0]
                ext = fsplit[1]
            else:
                name = file_
                ext = ""
            extn = len(ext)
            remain = 60 - extn
            name = name[:remain]
            new_path = ospath.join(dirpath, f"{name}{ext}")
            await rename(self._up_path, new_path)
            self._up_path = new_path
        return cap_mono

    def _get_input_media(self, subkey, key):
        rlist = []
        for msg in self._media_dict[key][subkey]:
            if key == "videos":
                input_media = InputMediaVideo(
                    media=msg.video.file_id, caption=msg.caption
                )
            else:
                input_media = InputMediaDocument(
                    media=msg.document.file_id, caption=msg.caption
                )
            rlist.append(input_media)
        return rlist

    async def _send_screenshots(self, dirpath, outputs):
        inputs = [
            InputMediaPhoto(ospath.join(dirpath, p), p.rsplit("/", 1)[-1])
            for p in outputs
        ]
        for i in range(0, len(inputs), 10):
            batch = inputs[i : i + 10]
            if Config.BOT_PM:
                await TgClient.bot.send_media_group(
                    chat_id=self._listener.user_id,
                    media=batch,
                    disable_notification=True,
                )
            self._sent_msg = (
                await self._sent_msg.reply_media_group(
                    media=batch,
                    quote=True,
                    disable_notification=True,
                )
            )[-1]

    async def _send_media_group(self, subkey, key, msgs):
        for index, msg in enumerate(msgs):
            if self._listener.hybrid_leech or not self._user_session:
                msgs[index] = await self._listener.client.get_messages(
                    chat_id=msg[0], message_ids=msg[1]
                )
            else:
                msgs[index] = await TgClient.user.get_messages(
                    chat_id=msg[0], message_ids=msg[1]
                )
        msgs_list = await msgs[0].reply_to_message.reply_media_group(
            media=self._get_input_media(subkey, key),
            quote=True,
            disable_notification=True,
        )
        for msg in msgs:
            if msg.link in self._msgs_dict:
                del self._msgs_dict[msg.link]
            await delete_message(msg)
        del self._media_dict[key][subkey]
        if self._listener.is_super_chat or self._listener.up_dest:
            for m in msgs_list:
                self._msgs_dict[m.link] = m.caption
        self._sent_msg = msgs_list[-1]

    async def _copy_media(self):
        try:
            if self._bot_pm:
                await TgClient.bot.copy_message(
                    chat_id=self._listener.user_id,
                    from_chat_id=self._sent_msg.chat.id,
                    message_id=self._sent_msg.id,
                    reply_to_message_id=(
                        self._listener.pm_msg.id if self._listener.pm_msg else None
                    ),
                )
        except Exception as err:
            if not self._listener.is_cancelled:
                LOGGER.error(f"Failed To Send in BotPM:\n{str(err)}")

    async def upload(self):
        await self._user_settings()
        res = await self._msg_to_reply()
        if not res:
            return
        is_log_del = False
        for dirpath, _, files in natsorted(await sync_to_async(walk, self._path)):
            if dirpath.strip().endswith("/yt-dlp-thumb"):
                continue
            if dirpath.strip().endswith("_mltbss"):
                await self._send_screenshots(dirpath, files)
                await rmtree(dirpath, ignore_errors=True)
                continue
            for file_ in natsorted(files):
                self._error = ""
                self._up_path = f_path = ospath.join(dirpath, file_)
                if not await aiopath.exists(self._up_path):
                    LOGGER.error(f"{self._up_path} not exists! Continue uploading!")
                    continue
                try:
                    f_size = await aiopath.getsize(self._up_path)
                    self._total_files += 1
                    if f_size == 0:
                        LOGGER.error(
                            f"{self._up_path} size is zero, telegram don't upload zero size files"
                        )
                        self._corrupted += 1
                        continue
                    if self._listener.is_cancelled:
                        return
                    cap_mono = await self._prepare_file(file_, dirpath)
                    if self._last_msg_in_group:
                        group_lists = [
                            x for v in self._media_dict.values() for x in v.keys()
                        ]
                        match = re_match(r".+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)", f_path)
                        if not match or match and match.group(0) not in group_lists:
                            for key, value in list(self._media_dict.items()):
                                for subkey, msgs in list(value.items()):
                                    if len(msgs) > 1:
                                        await self._send_media_group(subkey, key, msgs)
                    if self._listener.hybrid_leech and self._listener.user_transmission:
                        self._user_session = f_size > 2097152000
                        if self._user_session:
                            self._sent_msg = await TgClient.user.get_messages(
                                chat_id=self._sent_msg.chat.id,
                                message_ids=self._sent_msg.id,
                            )
                        else:
                            self._sent_msg = await self._listener.client.get_messages(
                                chat_id=self._sent_msg.chat.id,
                                message_ids=self._sent_msg.id,
                            )
                    self._last_msg_in_group = False
                    self._last_uploaded = 0
                    await self._upload_file(cap_mono, file_, f_path)
                    if self._log_msg and not is_log_del and Config.CLEAN_LOG_MSG:
                        await delete_message(self._log_msg)
                        is_log_del = True
                    if self._listener.is_cancelled:
                        return
                    if (
                        not self._is_corrupted
                        and (self._listener.is_super_chat or self._listener.up_dest)
                        and not self._is_private
                    ):
                        self._msgs_dict[self._sent_msg.link] = file_
                    await sleep(1)
                except Exception as err:
                    if isinstance(err, RetryError):
                        LOGGER.info(
                            f"Total Attempts: {err.last_attempt.attempt_number}"
                        )
                        err = err.last_attempt.exception()
                    LOGGER.error(f"{err}. Path: {self._up_path}", exc_info=True)
                    self._error = str(err)
                    self._corrupted += 1
                    if self._listener.is_cancelled:
                        return
                if not self._listener.is_cancelled and await aiopath.exists(
                    self._up_path
                ):
                    await remove(self._up_path)
        for key, value in list(self._media_dict.items()):
            for subkey, msgs in list(value.items()):
                if len(msgs) > 1:
                    try:
                        await self._send_media_group(subkey, key, msgs)
                    except Exception as e:
                        LOGGER.info(
                            f"While sending media group at the end of task. Error: {e}"
                        )
        if self._listener.is_cancelled:
            return
        if self._total_files == 0:
            await self._listener.on_upload_error(
                "No files to upload. In case you have filled EXCLUDED_EXTENSIONS, then check if all files have those extensions or not."
            )
            return
        if self._total_files <= self._corrupted:
            await self._listener.on_upload_error(
                f"Files Corrupted or unable to upload. {self._error or 'Check logs!'}"
            )
            return
        LOGGER.info(f"Leech Completed: {self._listener.name}")
        await self._listener.on_upload_complete(
            None, self._msgs_dict, self._total_files, self._corrupted
        )
        return

    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    async def _upload_file(self, cap_mono, file, o_path, force_document=False):
        if (
            self._thumb is not None
            and not await aiopath.exists(self._thumb)
            and self._thumb != "none"
        ):
            self._thumb = None
        thumb = self._thumb
        self._is_corrupted = False
        try:
            is_video, is_audio, is_image = await get_document_type(self._up_path)

            if not is_image and thumb is None:
                file_name = ospath.splitext(file)[0]
                thumb_path = f"{self._path}/yt-dlp-thumb/{file_name}.jpg"
                if await aiopath.isfile(thumb_path):
                    thumb = thumb_path
                elif is_audio and not is_video:
                    thumb = await get_audio_thumbnail(self._up_path)

                if thumb is None:
                    # Try auto thumbnail if enabled and no yt-dlp thumbnail found
                    user_dict = user_data.get(self._listener.user_id, {})
                    auto_thumb_enabled = user_dict.get("AUTO_THUMBNAIL")
                    if auto_thumb_enabled is None:
                        auto_thumb_enabled = Config.AUTO_THUMBNAIL

                    if auto_thumb_enabled and (is_video or is_audio):
                        try:
                            # Handle split files by using original filename for auto thumbnail
                            original_filename = (
                                await self._get_original_filename_for_thumbnail(file)
                            )
                            # Pass the enabled status to override config check
                            auto_thumb = (
                                await AutoThumbnailHelper.get_auto_thumbnail(
                                    original_filename,
                                    self._listener.user_id,
                                    enabled=True,
                                )
                            )
                            if auto_thumb:
                                thumb = auto_thumb
                                LOGGER.info(
                                    f"✅ Using auto thumbnail for: {file} (original: {original_filename})"
                                )
                            else:
                                LOGGER.info(
                                    f"❌ No auto thumbnail found for: {file}"
                                )
                        except Exception as e:
                            LOGGER.error(f"Error getting auto thumbnail: {e}")
                    elif not auto_thumb_enabled:
                        LOGGER.info(f"Auto thumbnail disabled for: {file}")
                    else:
                        LOGGER.info(
                            f"Auto thumbnail skipped - not video/audio: {file}"
                        )
            if (
                self._listener.as_doc
                or force_document
                or (not is_video and not is_audio and not is_image)
            ):
                key = "documents"
                if is_video and thumb is None:
                    # MODIFIED: Grid thumbnail logic for documents
                    if self._use_grid_thumb:
                        thumb = await get_multiple_frames_thumbnail(
                            self._up_path,
                            self._grid_layout,
                            False  # keep_screenshots
                        )
                    if thumb is None:  # Fallback to normal thumbnail
                        thumb = await get_video_thumbnail(self._up_path, None)

                if self._listener.is_cancelled:
                    return
                if thumb == "none":
                    thumb = None
                self._sent_msg = await self._sent_msg.reply_document(
                    document=self._up_path,
                    quote=True,
                    thumb=thumb,
                    caption=cap_mono,
                    force_document=True,
                    disable_notification=True,
                    progress=self._upload_progress,
                )
            elif is_video:
                key = "videos"
                duration = (await get_media_info(self._up_path))[0]
                
                # MODIFIED: Grid thumbnail logic for videos
                if thumb is None:
                    if self._use_grid_thumb:
                        # Use grid thumbnail (multiple frames)
                        thumb = await get_multiple_frames_thumbnail(
                            self._up_path,
                            self._grid_layout,
                            False  # keep_screenshots
                        )
                    elif self._listener.thumbnail_layout:
                        # Use listener's layout if specified
                        thumb = await get_multiple_frames_thumbnail(
                            self._up_path,
                            self._listener.thumbnail_layout,
                            self._listener.screen_shots,
                        )
                    
                    # Fallback to single frame thumbnail
                    if thumb is None:
                        thumb = await get_video_thumbnail(self._up_path, duration)
                
                if thumb is not None and thumb != "none":
                    with Image.open(thumb) as img:
                        width, height = img.size
                else:
                    width = 480
                    height = 320
                if self._listener.is_cancelled:
                    return
                if thumb == "none":
                    thumb = None
                self._sent_msg = await self._sent_msg.reply_video(
                    video=self._up_path,
                    quote=True,
                    caption=cap_mono,
                    duration=duration,
                    width=width,
                    height=height,
                    thumb=thumb,
                    supports_streaming=True,
                    disable_notification=True,
                    progress=self._upload_progress,
                )
            elif is_audio:
                key = "audios"
                duration, artist, title = await get_media_info(self._up_path)
                if self._listener.is_cancelled:
                    return
                if thumb == "none":
                    thumb = None
                self._sent_msg = await self._sent_msg.reply_audio(
                    audio=self._up_path,
                    quote=True,
                    caption=cap_mono,
                    duration=duration,
                    performer=artist,
                    title=title,
                    thumb=thumb,
                    disable_notification=True,
                    progress=self._upload_progress,
                )
            else:
                key = "photos"
                if self._listener.is_cancelled:
                    return
                self._sent_msg = await self._sent_msg.reply_photo(
                    photo=self._up_path,
                    quote=True,
                    caption=cap_mono,
                    disable_notification=True,
                    progress=self._upload_progress,
                )

            if (
                not self._listener.is_cancelled
                and self._media_group
                and (self._sent_msg.video or self._sent_msg.document)
            ):
                key = "documents" if self._sent_msg.document else "videos"
                if match := re_match(r".+(?=\.0*\d+$)|.+(?=\.part\d+\..+$)", o_path):
                    pname = match.group(0)
                    if pname in self._media_dict[key].keys():
                        self._media_dict[key][pname].append(
                            [self._sent_msg.chat.id, self._sent_msg.id]
                        )
                    else:
                        self._media_dict[key][pname] = [
                            [self._sent_msg.chat.id, self._sent_msg.id]
                        ]
                    msgs = self._media_dict[key][pname]
                    if len(msgs) == 10:
                        await self._send_media_group(pname, key, msgs)
                    else:
                        self._last_msg_in_group = True

            if self._sent_msg:
                await self._copy_media()

            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
        except (FloodWait, FloodPremiumWait) as f:
            LOGGER.warning(str(f))
            await sleep(f.value * 1.3)
            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
            return await self._upload_file(cap_mono, file, o_path)
        except Exception as err:
            if (
                self._thumb is None
                and thumb is not None
                and await aiopath.exists(thumb)
            ):
                await remove(thumb)
            err_type = "RPCError: " if isinstance(err, RPCError) else ""
            LOGGER.error(f"{err_type}{err}. Path: {self._up_path}", exc_info=True)
            if isinstance(err, BadRequest) and key != "documents":
                LOGGER.error(f"Retrying As Document. Path: {self._up_path}")
                return await self._upload_file(cap_mono, file, o_path, True)
            raise err

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except ZeroDivisionError:
            return 0

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def cancel_task(self):
        self._listener.is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.on_upload_error("your upload has been stopped!")

def extract_media_info(filename):
    """
    Extract media information from filename for Auto Rename feature

    Args:
        filename (str): Filename to parse

    Returns:
        tuple: (name, season, episode, year, part, volume)
    """
    import re

    # Remove file extension
    name_only = ospath.splitext(filename)[0]

    # Initialize variables
    name = ""
    season = None
    episode = None
    year = None
    part = None
    volume = None

    # Extract year (4 digits in parentheses or standalone)
    year_match = re.search(r"[\(\[]?(\d{4})[\)\]]?", name_only)
    if year_match:
        year = year_match.group(1)
        # Remove year from name for further processing
        name_only = name_only.replace(year_match.group(0), "").strip()

    # Extract season and episode patterns
    # Pattern: S01E01, S1E1, Season 1 Episode 1, 1x01, etc.
    se_patterns = [
        r"[Ss](\d+)[Ee](\d+)",  # S01E01, s01e01
        r"[Ss]eason\s*(\d+)\s*[Ee]pisode\s*(\d+)",  # Season 1 Episode 1
        r"(\d+)x(\d+)",  # 1x01
    ]

    for pattern in se_patterns:
        match = re.search(pattern, name_only)
        if match:
            season = match.group(1)
            episode = match.group(2)
            # Remove season/episode from name
            name_only = name_only.replace(match.group(0), "").strip()
            break

    # Extract part number
    part_match = re.search(r"[Pp]art\s*(\d+)", name_only)
    if part_match:
        part = part_match.group(1)
        name_only = name_only.replace(part_match.group(0), "").strip()

    # Extract volume
    vol_match = re.search(r"[Vv]ol(?:ume)?\s*(\d+)", name_only)
    if vol_match:
        volume = vol_match.group(1)
        name_only = name_only.replace(vol_match.group(0), "").strip()

    # Clean up the remaining name
    # Remove quality indicators
    name_only = re.sub(
        r"\b(480p|720p|1080p|2160p|4k|8k)\b", "", name_only, flags=re.IGNORECASE
    )
    # Remove codec/format indicators
    name_only = re.sub(
        r"\b(x264|x265|h264|h265|hevc|avc|10bit|8bit)\b",
        "",
        name_only,
        flags=re.IGNORECASE,
    )
    # Remove release groups (usually in square brackets)
    name_only = re.sub(r"\[.*?\]", "", name_only)
    # Remove source indicators
    name_only = re.sub(
        r"\b(BluRay|BRRip|WEB-DL|WEBRip|HDTV|DVDRip|BDRip|WEB)\b",
        "",
        name_only,
        flags=re.IGNORECASE,
    )
    # Remove extra indicators
    name_only = re.sub(
        r"\b(REPACK|PROPER|REAL|RERIP)\b", "", name_only, flags=re.IGNORECASE
    )
    # Replace dots, underscores, and hyphens with spaces
    name_only = re.sub(r"[._-]+", " ", name_only)
    # Remove multiple spaces
    name_only = re.sub(r"\s+", " ", name_only).strip()

    name = name_only if name_only else "Unknown"

    return name, season, episode, year, part, volume
