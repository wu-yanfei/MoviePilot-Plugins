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


class SyncSoftLink(_PluginBase):
    # 插件名称
    plugin_name = "同步软链接"
    # 插件描述
    plugin_desc = "利用rclone定时同步云盘和本地软连接，删除失效的软连接，添加新增的软连接。"
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
    _rclone_exe = None  # "rclone"  # 如果rclone不在系统PATH中，请指定完整路径
    _remote_path = None  # "MP:/115_share/media_center"
    _local_path = None  # "/115_share/media_center" # 本地操作的基础路径
    _link_target_prefix = None  # "/media_center/CloudNAS/WebDAV" # 新软链接的目标前缀

    _dry_run = False  # 设置为 False 来实际执行操作，True 只打印将要执行的操作

    def init_plugin(self, config: dict = None):
        logger.info(f"插件初始化")
        if config:
            self._enabled = config.get("enabled")
            self._cron = config.get("cron")
            self._rclone_exe = config.get("rclone_exe")
            self._remote_path = config.get("remote_path")
            self._local_path = config.get("local_path")
            self._link_target_prefix = config.get("link_target_prefix")

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        if self._enabled and self._cron:
            return [
                {
                    "id": "SyncSoftLink",
                    "name": "软连接同步服务",
                    "trigger": CronTrigger.from_crontab(self._cron),
                    "func": self._main,
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
                                            'model': 'rclone_exe',
                                            'label': 'rclone执行程序位置'
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
                                            'model': 'remote_path',
                                            'label': '远程目录'
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
                                            'model': 'local_path',
                                            'label': '本地目录'
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
                                            'model': 'link_target_prefix',
                                            'label': '软连接前缀'
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
            "rclone_exe": "rclone",
            "remote_path": "",
            "local_path": "",
            "link_target_prefix": ""
        }

    def get_state(self) -> bool:
        return self._enabled

    def get_page(self) -> List[dict]:
        pass

    def _find_file(self, target_path):
        # Ensure the input is an absolute path
        target_path = os.path.abspath(target_path)
        
        # Split the path into parts
        path_parts = target_path.split(os.sep)
        
        # Start from the root directory
        current_path = os.sep
        
        # Traverse directories from root to the parent of the target file
        for part in path_parts[1:-1]:  # Skip empty root and last component
            current_path = os.path.join(current_path, part)
            
            # Refresh directory contents
            try:
                time.sleep(2)
                os.listdir(current_path)
            except FileNotFoundError:
                return None
                
            if not os.path.isdir(current_path):
                return None
        
        # Check for the target file in the final directory
        target_file = os.path.join(current_path, path_parts[-1])
        if os.path.isfile(target_file):
            return target_file
        return None

    def _run_command(self, command_args):
        """执行外部命令并返回其输出和返回码"""
        try:
            process = subprocess.Popen(command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       encoding='utf-8')
            stdout, stderr = process.communicate()
            return stdout, stderr, process.returncode
        except FileNotFoundError:
            logger.info(f"错误：找不到命令 '{command_args[0]}'. 请确保它已安装并在PATH中。")
            sys.exit(1)
        except Exception as e:
            logger.info(f"执行命令 '{' '.join(command_args)}' 时发生错误: {e}")
            return None, str(e), 1

    def _parse_rclone_lsjson_output(self, json_str: str) -> set:
        """
        解析 'rclone lsjson -R' 的JSON输出。
        返回一个包含相对路径的集合，目录以 '/' 结尾。
        """
        items = set()
        if not json_str:
            return items
        try:
            file_list = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"无法解析 rclone lsjson 输出: {e}")
            logger.error(f"接收到的输出: {json_str[:500]}...")  # Log the beginning of the problematic string
            return items

        for item in file_list:
            item_path = item.get("Path")
            if not item_path:
                continue

            # 检查并去除 .rclonelink 后缀
            if item_path.endswith('.rclonelink'):
                item_path = item_path[:-len('.rclonelink')]

            # 为目录添加末尾的斜杠
            if item.get("IsDir"):
                item_path += '/'

            items.add(item_path)

        return items

    def _get_rclone_lsjson_items(self, rclone_target_path, is_remote=True):
        """使用 rclone lsjson 获取目录内容（相对路径集合）。"""
        logger.info(f"正在获取 {'远程' if is_remote else '本地'} 目录内容: {rclone_target_path} ... (使用 lsjson)")
        # 使用 -R 进行递归列出
        cmd = [self._rclone_exe, "--tpslimit", "3", "lsjson", "-R", rclone_target_path, "-l", "--fast-list"]
        stdout, stderr, returncode = self._run_command(cmd)

        if returncode != 0:
            logger.info(f"错误：获取 {'远程' if is_remote else '本地'} 目录内容 '{rclone_target_path}' 失败。")
            logger.info(f"Rclone Stderr:\n{stderr}")
            sys.exit(1)
        logger.info(f"{'远程' if is_remote else '本地'} 目录内容获取成功。")
        return self._parse_rclone_lsjson_output(stdout)

    # --- 主逻辑 ---
    def _main(self):
        # 确保本地基础路径存在，如果不存在则创建它
        if not os.path.exists(self._local_path):
            if not self._dry_run:
                try:
                    os.makedirs(self._local_path)
                    logger.info(f"已创建本地基础目录: {self._local_path}")
                except Exception as e:
                    logger.info(f"错误: 创建本地基础目录 {self._local_path} 失败: {e}")
                    sys.exit(1)
            else:
                logger.info(f"DRY RUN: (如果不存在，将创建本地基础目录: {self._local_path})")

        logger.info("\n开始同步过程...")
        if self._dry_run:
            logger.info("！！！当前为 DRY RUN 模式，不会执行任何实际的文件系统更改。！！！")

        # 1. 获取远程目录内容
        remote_items = self._get_rclone_lsjson_items(self._remote_path, is_remote=True)

        # 2. 获取本地目录内容
        local_items = self._get_rclone_lsjson_items(self._local_path, is_remote=False)

        logger.info(f"远程条目数: {len(remote_items)}")
        logger.info(f"本地条目数: {len(local_items)}")

        # 3. 找出本地多余的（远程没有的）
        items_to_delete_locally = local_items - remote_items
        # 为了安全删除，从深到浅排序
        sorted_items_to_delete = sorted(list(items_to_delete_locally), key=len, reverse=True)

        # 4. 找出本地没有的（远程有的）
        items_to_create_locally = remote_items - local_items
        # 为了安全创建，从浅到深排序
        sorted_items_to_create = sorted(list(items_to_create_locally), key=len)

        # 5. 执行删除操作
        logger.info("\n--- 开始删除本地多余的文件和文件夹 ---")
        if not sorted_items_to_delete:
            logger.info("没有需要删除的本地条目。")
        for item_rel_path in sorted_items_to_delete:
            local_item_full_path = os.path.join(self._local_path, item_rel_path.lstrip('/'))
            logger.info(f"准备删除: {local_item_full_path}")
            if not self._dry_run:
                try:
                    if os.path.islink(local_item_full_path) or os.path.isfile(local_item_full_path):
                        os.unlink(local_item_full_path)
                        logger.info(f"  已删除链接或文件: {local_item_full_path}")
                    elif os.path.isdir(local_item_full_path):
                        shutil.rmtree(local_item_full_path)
                        logger.info(f"  已删除目录: {local_item_full_path}")
                    else:
                        logger.info(f"  警告: 尝试删除时未找到 {local_item_full_path} (可能已被父目录删除)")
                except Exception as e:
                    logger.info(f"  错误: 删除 {local_item_full_path} 失败: {e}")
            else:
                logger.info(f"  DRY RUN: 将删除 {local_item_full_path}")

        # 6. 执行新增操作 (创建软链接或真实目录)
        logger.info("\n--- 开始新增本地没有的文件和文件夹 ---")
        if not sorted_items_to_create:
            logger.info("没有需要新增的本地条目。")
        for item_rel_path in sorted_items_to_create:
            if item_rel_path.endswith('/'):
                # 这是一个目录，创建真实的本地目录
                local_dir_path = os.path.join(self._local_path, item_rel_path.rstrip('/'))
                logger.info(f"准备创建真实目录: {local_dir_path}")
                if not self._dry_run:
                    try:
                        os.makedirs(local_dir_path, exist_ok=True)
                        logger.info(f"  已创建真实目录: {local_dir_path}")
                    except Exception as e:
                        logger.info(f"  错误: 创建真实目录 {local_dir_path} 失败: {e}")
                else:
                    logger.info(f"  DRY RUN: 将创建真实目录 {local_dir_path}")
            else:
                # 这是一个文件，创建软链接
                link_name_rel = item_rel_path.rstrip('/')
                link_full_path = os.path.join(self._local_path, link_name_rel)

                link_target_full_path = os.path.join(self._link_target_prefix, self._local_path.lstrip('/'),
                                                     link_name_rel)

                logger.info(f"准备创建软链接: {link_full_path} -> {link_target_full_path}")

                if not self._dry_run:
                    try:
                        link_parent_dir = os.path.dirname(link_full_path)
                        os.makedirs(link_parent_dir, exist_ok=True)

                        if os.path.exists(link_full_path) or os.path.islink(link_full_path):
                            logger.info(f"  警告: 路径 {link_full_path} 已存在，跳过创建。")
                        else:
                            # 模拟刷新
                            if not self._find_file(link_target_full_path):
                                logger.info(f"入库文件在挂载路径刷新失败，请手动尝试")
                            else:
                                time.sleep(10)
                                os.symlink(link_target_full_path, link_full_path)
                                logger.info(f"  已创建软链接: {link_full_path} -> {link_target_full_path}")
                    except Exception as e:
                        logger.info(f"  错误: 创建软链接 {link_full_path} 失败: {e}")
                else:
                    logger.info(f"  DRY RUN: 将创建软链接 {link_full_path} -> {link_target_full_path}")

        if self._dry_run:
            logger.info("\n！！！DRY RUN 结束。没有实际更改文件系统。！！！")
        logger.info("\n同步过程结束。")

    def stop_service(self):
        """
        退出插件
        """
        pass