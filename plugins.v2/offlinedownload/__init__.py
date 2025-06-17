import os
import json
from typing import List, Tuple, Dict, Any

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType

from p115client import P115Client

class SyncSoftLink(_PluginBase):
    # 插件名称
    plugin_name = "115离线下载"
    # 插件描述
    plugin_desc = "通过命令触发115网盘的离线下载任务。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wu-yanfei/MoviePilot-Plugins/main/icons/softlink.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "wu-yanfei"
    # 作者主页
    author_url = "https://github.com/wu-yanfei"
    # 插件配置项ID前缀
    plugin_config_prefix = "offlinedownload_"
    # 加载顺序
    plugin_order = 5
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _115_cookie = None
    _115_path = None

    def init_plugin(self, config: dict = None):
        logger.info(f"插件初始化")
        if config:
            self._enabled = config.get("enabled")
            self._115_cookie = config.get("115_cookie")
            self._115_path = config.get("115_path")

    def get_command(self) -> List[Dict[str, Any]]:
        """
        返回插件支持的命令列表
        """
        return [{
            "cmd": "/offline_download",
            "event": EventType.PluginAction,
            "desc": "115离线下载",
            "category": "",
            "data": {
                "action": "offline_download"
            }
        }]

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        return []

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
                                    'md': 4
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': '115_cookie',
                                            'label': '115 Cookie (UID=...; CID=...; SEID=...)'
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
                                            'model': '115_path',
                                            'label': '115文件夹CID'
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
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '输入 /offline_download <URL> 触发离线下载任务'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            "115_cookie": "",
            "115_path": ""
        }

    def get_state(self) -> bool:
        return self._enabled

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.PluginAction)
    def offline_download(self, event: Event):
        """
        处理 /offline_download 命令，触发115网盘离线下载
        """
        if not self._enabled:
            logger.error("插件未启用")
            event.event_data["result"] = {"success": False, "message": "插件未启用"}
            return

        if not all([self._115_cookie, self._115_path]):
            logger.error("配置项缺失，无法执行离线下载")
            event.event_data["result"] = {"success": False, "message": "配置项缺失"}
            return

        # 获取命令参数（URL）
        command_args = event.event_data.get("args", "")
        if not command_args:
            logger.error("未提供下载URL")
            event.event_data["result"] = {"success": False, "message": "未提供下载URL"}
            return

        url = command_args.strip()
        if not url.startswith(("http://", "https://", "ftp://", "magnet:", "ed2k://")):
            logger.error(f"无效的URL: {url}")
            event.event_data["result"] = {"success": False, "message": f"无效的URL: {url}"}
            return

        # 初始化115客户端
        try:
            client = P115Client(self._115_cookie)
        except Exception as e:
            logger.error(f"初始化115客户端失败: {e}")
            event.event_data["result"] = {"success": False, "message": f"初始化115客户端失败: {e}"}
            return

        # 准备离线下载任务
        payload = {
            "url": url,
            "wp_path_id": int(self._115_path),
            "savepath": ""  # 默认保存到根目录
        }

        try:
            result = client.offline_add_url(payload, use_web_api=False)
            logger.info(f"离线下载任务添加成功: {url}, 结果: {json.dumps(result, ensure_ascii=False)}")
            event.event_data["result"] = {"success": True, "message": "离线下载任务添加成功", "data": result}
        except Exception as e:
            logger.error(f"添加离线下载任务失败: {e}")
            event.event_data["result"] = {"success": False, "message": f"添加离线下载任务失败: {e}"}

    def stop_service(self):
        """
        退出插件
        """
        pass