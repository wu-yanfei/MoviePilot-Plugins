import os
import time
import subprocess
import sys
import shutil
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any

from app.core.context import MediaInfo
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import TransferInfo, FileItem
from app.schemas.types import EventType, MediaType
from apscheduler.triggers.cron import CronTrigger

from p115client import P115Client
from p115client.tool.export_dir import (
    export_dir_parse_iter,
    parse_export_dir_as_path_iter,
)

class SyncSoftLink(_PluginBase):
    # 插件名称
    plugin_name = "同步软链接"
    # 插件描述
    plugin_desc = "对接115网盘，删除失效的软连接，添加新增的软连接。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/wu-yanfei/MoviePilot-Plugins/main/icons/softlink.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "wu-yanfei"
    # 作者主页
    author_url = "https://github.com/wu-yanfei"
    # 插件配置项ID前缀
    plugin_config_prefix = "syncsoftlink_"
    # 加载顺序
    plugin_order = 5
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _cron = None
    _115_cookie = None
    _115_path = None
    _fuse_path_prefix = None
    _softlink_path_prefix = None

    _dry_run = False  # 设置为 False 来实际执行操作，True 只打印将要执行的操作

    def init_plugin(self, config: dict = None):
        logger.info(f"插件初始化")
        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._115_cookie = config.get("115_cookie")
            self._115_path = config.get("115_path")
            self._fuse_path_prefix = config.get("fuse_path_prefix")
            self._softlink_path_prefix = config.get("softlink_path_prefix")

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        if self._enabled and self._cron:
            return [
                {
                    "id": "SyncSoftLink",
                    "name": "软连接同步服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self.__main,
                    "kwargs": {}
                }
            ]
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
                                            'model': 'cron',
                                            'label': '定时',
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
                                            'label': 'UID=...; CID=...; SEID=...'
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
                                            'model': '115_path',
                                            'label': '115文件夹CID'
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
                                            'model': 'fuse_path_prefix',
                                            'label': '挂载路径前缀'
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
                                            'model': 'softlink_path_prefix',
                                            'label': '软连接路径前缀'
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
                                            'text': '暂无。'
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
            "cron": "0 9 * * *",
            "115_cookie": "",
            "115_path": "",
            "fuse_path_prefix": "",
            "softlink_path_prefix": ""
        }

    def get_state(self) -> bool:
        return self._enabled

    def get_page(self) -> List[dict]:
        pass

    def local_dir_as_path_iter(self, root_path: str):
        """
        遍历本地文件夹，生成每个文件和子文件夹的完整路径字符串。
        
        :param root_path: 本地文件夹的根路径。
        """
        root_path = os.path.normpath(root_path)
        yield root_path
        for dirpath, dirnames, filenames in os.walk(root_path):
            for dirname in dirnames:
                yield os.path.join(dirpath, dirname)
            for filename in filenames:
                yield os.path.join(dirpath, filename)

    def simulate_refresh(self, mount_path: str):
        """
        逐层访问挂载路径以模拟刷新。
        
        :param mount_path: 需要刷新的挂载路径。
        """
        path_parts = Path(mount_path).parts
        current_path = path_parts[0]
        for part in path_parts[1:]:
            current_path = os.path.join(current_path, part)
            if os.path.exists(current_path):
                try:
                    os.listdir(current_path)
                    logger.info(f"刷新路径: {current_path}")
                except Exception as e:
                    logger.warning(f"刷新路径 {current_path} 失败: {e}")
            else:
                break

    def __main(self):
        """
        主逻辑：同步115网盘目录与本地软连接目录。
        """
        if not all([self._115_cookie, self._115_path, self._fuse_path_prefix, self._softlink_path_prefix]):
            logger.error("配置项缺失，无法执行同步")
            return

        # 初始化115客户端
        try:
            client = P115Client(self._115_cookie)
        except Exception as e:
            logger.error(f"初始化115客户端失败: {e}")
            return

        # 获取115网盘目录树
        logger.info("开始获取115网盘目录树...")
        try:
            path_iterator = export_dir_parse_iter(
                client=client,
                export_file_ids=int(self._115_path),
                target_pid=0,
                parse_iter=parse_export_dir_as_path_iter,
                show_clock=True
            )
            cloud_paths = set(path_iterator)
            logger.info(f"获取到 {len(cloud_paths)} 个云端项目")
        except Exception as e:
            logger.error(f"获取115网盘目录树失败: {e}")
            return

        # 获取本地软连接目录树
        softlink_root = os.path.join(self._softlink_path_prefix, "media_center")
        logger.info("开始获取本地软连接目录树...")
        local_paths = set(self.local_dir_as_path_iter(softlink_root))
        logger.info(f"获取到 {len(local_paths)} 个本地项目")

        # 规范化路径为相对路径
        cloud_root = min(cloud_paths, key=len)  # 云端根路径，例如 /media_center
        # 转换为相对路径集合
        cloud_rel_paths = {os.path.relpath(p, cloud_root) if p != cloud_root else "." for p in cloud_paths}
        local_rel_paths = {os.path.relpath(p, softlink_root) if p != softlink_root else "." for p in local_paths}

        # 计算需要添加和删除的相对路径
        to_add_rel = cloud_rel_paths - local_rel_paths
        to_remove_rel = local_rel_paths - cloud_rel_paths

        # 删除多余的软连接或目录
        for rel_path in sorted(to_remove_rel, reverse=True):  # 从深到浅删除
            path = softlink_root if rel_path == "." else os.path.join(softlink_root, rel_path)
            if self._dry_run:
                logger.info(f"[Dry Run] 将删除: {path}")
            else:
                try:
                    if os.path.islink(path) or os.path.isfile(path):
                        os.remove(path)
                        logger.info(f"删除文件/软连接: {path}")
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        logger.info(f"删除目录: {path}")
                except Exception as e:
                    logger.error(f"删除 {path} 失败: {e}")

        # 添加缺失的目录或软连接
        for rel_path in sorted(to_add_rel):  # 从浅到深创建
            cloud_path = cloud_root if rel_path == "." else os.path.join(cloud_root, rel_path)
            softlink_path = softlink_root if rel_path == "." else os.path.join(softlink_root, rel_path)
            mount_path = os.path.join(self._fuse_path_prefix, "media_center", rel_path if rel_path != "." else "")

            if self._dry_run:
                if "." not in os.path.basename(cloud_path):
                    logger.info(f"[Dry Run] 将创建目录: {softlink_path}")
                else:
                    logger.info(f"[Dry Run] 将创建软连接: {softlink_path} -> {mount_path}")
                continue

            # 模拟刷新挂载路径
            self.simulate_refresh(os.path.dirname(mount_path))

            try:
                # 创建父目录
                os.makedirs(os.path.dirname(softlink_path) if rel_path != "." else softlink_root, exist_ok=True)

                # 判断是否为文件（基于是否有 . 后缀）
                if "." not in os.path.basename(cloud_path):
                    # 创建普通目录
                    os.makedirs(softlink_path, exist_ok=True)
                    logger.info(f"创建目录: {softlink_path}")
                else:
                    # 创建软连接
                    if os.path.exists(softlink_path):
                        os.remove(softlink_path)
                    os.symlink(mount_path, softlink_path)
                    logger.info(f"创建软连接: {softlink_path} -> {mount_path}")
            except Exception as e:
                logger.error(f"处理 {softlink_path} 失败: {e}")

        logger.info("软连接同步完成")

    def stop_service(self):
        """
        退出插件
        """
        pass