import os
import time
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
    _delay = None
    _alist_path = None
    _cd2_path = None
    _softlink_path = None

    def init_plugin(self, config: dict = None):
        logger.info(f"插件初始化")
        if config:
            self._enabled = config.get("enabled")
            self._delay = config.get("delay")
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
                            },
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
                                            'model': 'delay',
                                            'label': '延迟时间'
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
            "delay": "",
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

    def find_file(self, new_file_path):
        # 将目标文件路径转为绝对路径
        target_path = os.path.abspath(new_file_path)
        current_path = os.path.abspath(self._cd2_path)
             
        # 获取目标文件路径的各个部分
        path_parts = target_path[len(current_path):].lstrip(os.sep).split(os.sep)
        
        # 依次进入每一级目录
        for part in path_parts[:-1]:  # 处理到倒数第二层
            time.sleep(2)
            current_path = os.path.join(current_path, part)
            
            # 刷新当前目录的内容
            try:
                os.listdir(current_path)
            except FileNotFoundError:
                return None
            
            if not os.path.isdir(current_path):
                return None
        
        # 现在 current_path 是目标目录，检查目标文件
        target_file = os.path.join(current_path, path_parts[-1])
        if os.path.isfile(target_file):
            return target_file
        else:
            return None

    @eventmanager.register(EventType.TransferComplete)
    def download(self, event: Event):
        """
        调用AutoSoftLink生成软链接
        """
        if not self._enabled or not self._alist_path or not self._cd2_path or not self._softlink_path or not self._delay:
            return
        event_info: dict = event.event_data
        if not event_info:
            return

        # 入库数据
        transferinfo: TransferInfo = event_info.get("transferinfo")

        # 媒体库Alist文件路径
        file_path = transferinfo.target_item.path
        logger.info(f"{self._delay}秒后处理：{file_path}")
        time.sleep(int(self._delay))
        logger.info(f"开始处理：{file_path}")

        if file_path.startswith(self._alist_path):
            logger.info(f"测试开始")
            new_file_path = file_path.replace(self._alist_path, self._cd2_path, 1)
            
            relative_path = os.path.relpath(file_path, self._alist_path)
            
            symlink_target = os.path.join(self._softlink_path, relative_path)

            os.makedirs(os.path.dirname(symlink_target), exist_ok=True)
            logger.info(f"测试结束")

            # 模拟刷新
            if not find_file(new_file_path):
                logger.info(f"入库文件在cd2路径刷新失败，请手动尝试")
                return
            time.sleep(10)

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
