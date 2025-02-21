import os
from pathlib import Path
from typing import List, Tuple, Dict, Any

from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import TransferInfo, FileItem
from app.schemas.types import EventType, MediaType


class AutoSoftLink(_PluginBase):
    # 插件名称
    plugin_name = "自动软链接"
    # 插件描述
    plugin_desc = "整理入库时生成软链接。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wu-yanfei/MoviePilot-Plugins/main/icons/softlink.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "wu-yanfei"
    # 作者主页
    author_url = "https://github.com/wu-yanfei"
    # 插件配置项ID前缀
    plugin_config_prefix = "autosoftlink_"
    # 加载顺序
    plugin_order = 5
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _softlink_path = None

    def init_plugin(self, config: dict = None):
        logger.info(f"插件初始化")
        if config:
            self._enabled = config.get("enabled")
            self._softlink_path = config.get("softlink_path")

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'softlink_path',
                                            'label': '软链接路径'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "softlink_path": ""
        }

    def get_state(self) -> bool:
        return self._enabled

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        pass

    @eventmanager.register(EventType.TransferComplete)
    def download(self, event: Event):
        """
        调用AutoSoftLink生成软链接
        """
        # if not self._enabled or not self._softlink_path:
        #     return
        # item = event.event_data
        # if not item:
        #     return

        # 媒体信息
        item_media: MediaInfo = item.get("mediainfo")
        # 转移信息
        item_transfer: TransferInfo = item.get("transferinfo")
        # 类型
        item_type = item_media.type
        # 目的路径
        item_dest: FileItem = item_transfer.target_diritem
        # 文件清单
        item_file_list = item_transfer.file_list_new

        logger.info("检测到转移完成")



