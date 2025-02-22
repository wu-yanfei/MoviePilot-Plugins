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
    _alist_path = None
    _cd2_path = None
    _softlink_path = None

    def init_plugin(self, config: dict = None):
        logger.info(f"插件初始化")
        if config:
            self._enabled = config.get("enabled")
            self._alist_path = config.get("alist_path")
            self._cd2_path = config.get("cd2_path")
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'alist_path',
                                            'label': 'alist路径'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cd2_path',
                                            'label': 'cd2路径'
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
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
            "alist_path": "",
            "cd2_path": "",
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
        logger.info(f"alist路径：{self._alist_path}")
        logger.info(f"cd2路径：{self._cd2_path}")
        logger.info(f"软链接路径：{self._softlink_path}")

        # if not self._enabledor or not self._alist_path or not self._cd2_path or not self._softlink_path:
        #     return
        event_info: dict = event.event_data
        # if not event_info:
        #     return

        # 入库数据
        transferinfo: TransferInfo = event_info.get("transferinfo")

        # 媒体库Alist文件路径
        file_path = transferinfo.target_item.path
        logger.info(f"新增文件：{file_path}")

        if file_path.startswith(self._alist_path):
            new_file_path = file_path.replace(self._alist_path, self._cd2_path, 1)
            
            relative_path = os.path.relpath(file_path, self._alist_path)
            
            symlink_target = os.path.join(self._softlink_path, relative_path)

            os.makedirs(os.path.dirname(symlink_target), exist_ok=True)

            if not os.path.exists(symlink_target):
                os.symlink(new_file_path, symlink_target)
                logger.info(f"生成软链接成功: {symlink_target} -> {new_file_path}")
            else:
                logger.info(f"生成软链接失败: {symlink_target}")
        else:
            logger.info("文件匹配失败，请检查参数")

    def stop_service(self):
        """
        退出插件
        """
        pass
