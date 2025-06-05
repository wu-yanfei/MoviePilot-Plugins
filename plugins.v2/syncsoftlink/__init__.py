import os
import time
import subprocess
import sys
import shutil
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
    _rclone_exe = None # "rclone"  # 如果rclone不在系统PATH中，请指定完整路径
    _remote_path = None # "MP:/115_share/media_center"
    _local_path = None # "/115_share/media_center" # 本地操作的基础路径
    _link_target_prefix = None # "/media_center/CloudNAS/WebDAV" # 新软链接的目标前缀

    _dry_run = True # 设置为 False 来实际执行操作，True 只打印将要执行的操作

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
                                        'component': 'VSwitch',
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

    def stop_service(self):
        pass

    def _run_command(command_args):
        """执行外部命令并返回其输出和返回码"""
        try:
            process = subprocess.Popen(command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            return stdout, stderr, process.returncode
        except FileNotFoundError:
            logger.info(f"错误：找不到命令 '{command_args[0]}'. 请确保它已安装并在PATH中。")
            sys.exit(1)
        except Exception as e:
            logger.info(f"执行命令 '{' '.join(command_args)}' 时发生错误: {e}")
            return None, str(e), 1

    def _parse_rclone_tree_output(output_str):
        """
        解析 rclone tree --noindent 的输出。
        返回一个集合，包含相对于基础路径的文件和目录的相对路径。
        目录以 '/' 结尾。
        """
        items = set()
        if not output_str:
            return items
        lines = output_str.strip().split('\n')
        for line in lines:
            # --noindent 输出的是相对于 tree 命令给定路径的相对路径
            # 我们需要处理好文件和目录的表示
            # rclone tree 通常会给目录名添加末尾的 '/'
            item_path = line.strip()
            if item_path: # 确保不是空行
                items.add(item_path)
        return items

    def _get_rclone_tree_items(self, rclone_target_path, is_remote=True):
        """获取指定rclone路径的目录树内容（相对路径集合）"""
        logger.info(f"正在获取 {'远程' if is_remote else '本地'} 目录树: {rclone_target_path} ...")
        # 使用 --noindent 来移除缩进，简化解析
        # 使用 -L 999 (或足够大的数字) 来确保获取所有层级
        # 使用 --dirs-first 可能有助于调试，但对于集合操作顺序不重要
        # 使用 --files-only 和 --dirs-only 分别获取再合并也可以，但直接解析tree更通用
        cmd = [self._rclone_exe, "tree", "--noindent", "-L", "999", rclone_target_path]
        stdout, stderr, returncode = self._run_command(cmd)

        if returncode != 0:
            logger.info(f"错误：获取 {'远程' if is_remote else '本地'} 目录树 '{rclone_target_path}' 失败。")
            logger.info(f"Rclone Stderr:\n{stderr}")
            if is_remote: # 如果远程获取失败，则按要求退出
                sys.exit(1)
            return None # 本地获取失败则返回None，后续处理
        logger.info(f"{'远程' if is_remote else '本地'} 目录树获取成功。")
        return self._parse_rclone_tree_output(stdout)

    # --- 主逻辑 ---
    def _main(self):
        # 确保本地基础路径存在，如果不存在则创建它
        # 这对于 rclone tree 本地 和 后续创建软链接的父目录是必要的
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

        logger.info("开始同步过程...")
        if self._dry_run:
            logger.info("！！！当前为 DRY RUN 模式，不会执行任何实际的文件系统更改。！！！")

        # 1. 获取远程目录树
        remote_items = self._get_rclone_tree_items(self._remote_path, is_remote=True)
        # 如果 get_rclone_tree_items 因远程失败而退出，这里不会执行

        # 2. 获取本地目录树
        # 对于本地路径，rclone tree 也适用
        local_items = self._get_rclone_tree_items(self._local_path, is_remote=False)
        if local_items is None:
            logger.info("错误：无法获取本地目录树，程序终止。")
            sys.exit(1)

        logger.info(f"远程条目数: {len(remote_items)}")
        logger.info(f"本地条目数: {len(local_items)}")

        # 3. 找出本地多余的（远程没有的）
        items_to_delete_locally = local_items - remote_items
        # 为了安全删除，从深到浅排序（先删除文件，再删除空目录）
        # 对于软链接，直接删除即可，但如果本地混杂了真实目录，排序有助于shutil.rmtree
        sorted_items_to_delete = sorted(list(items_to_delete_locally), key=len, reverse=True)


        # 4. 找出本地没有的（远程有的）
        items_to_create_locally = remote_items - local_items
        # 为了安全创建，从浅到深排序（先创建父目录，虽然os.makedirs会处理）
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
                    if os.path.islink(local_item_full_path):
                        os.unlink(local_item_full_path)
                        logger.info(f"  已删除软链接: {local_item_full_path}")
                    elif os.path.isdir(local_item_full_path): # 如果是真实目录（不应出现，但以防万一）
                        shutil.rmtree(local_item_full_path)
                        logger.info(f"  已删除目录 (非软链): {local_item_full_path}")
                    elif os.path.exists(local_item_full_path): # 如果是真实文件（不应出现）
                        os.remove(local_item_full_path)
                        logger.info(f"  已删除文件 (非软链): {local_item_full_path}")
                    else:
                        logger.info(f"  警告: 尝试删除时未找到 {local_item_full_path} (可能已被父目录删除)")
                except Exception as e:
                    logger.info(f"  错误: 删除 {local_item_full_path} 失败: {e}")
            else:
                logger.info(f"  DRY RUN: 将删除 {local_item_full_path}")

        # 6. 执行新增操作 (创建软链接)
        logger.info("\n--- 开始新增本地没有的文件和文件夹 (创建软链接) ---")
        if not sorted_items_to_create:
            logger.info("没有需要新增的本地条目。")
        for item_rel_path in sorted_items_to_create:
            # item_rel_path 是从 rclone tree 获取的，可能是 dir/ 或 file.txt
            # 软链接名不应以 / 结尾
            link_name_rel = item_rel_path.rstrip('/')
            link_full_path = os.path.join(self._local_path, link_name_rel)

            # 软链接的目标路径段也使用不带末尾斜杠的相对路径
            target_path_segment = item_rel_path.rstrip('/')
            link_target_full_path = os.path.join(self._link_target_prefix, target_path_segment)

            logger.info(f"准备创建软链接: {link_full_path} -> {link_target_full_path}")

            if not self._dry_run:
                try:
                    # 确保软链接所在的目录存在
                    link_parent_dir = os.path.dirname(link_full_path)
                    if not os.path.exists(link_parent_dir):
                        os.makedirs(link_parent_dir)
                        logger.info(f"  已创建父目录: {link_parent_dir}")

                    # 创建软链接
                    if os.path.exists(link_full_path) or os.path.islink(link_full_path):
                        logger.info(f"  警告: 路径 {link_full_path} 已存在，跳过创建。")
                    else:
                        os.symlink(link_target_full_path, link_full_path)
                        logger.info(f"  已创建软链接: {link_full_path} -> {link_target_full_path}")
                except Exception as e:
                    logger.info(f"  错误: 创建软链接 {link_full_path} 失败: {e}")
            else:
                logger.info(f"  DRY RUN: 将创建软链接 {link_full_path} -> {link_target_full_path}")
                link_parent_dir = os.path.dirname(link_full_path)
                if not os.path.exists(link_parent_dir) and not os.path.isdir(self._local_path): # 避免在dry run时对根目录也判断
                    # 模拟创建父目录的情况
                    is_parent_relative_to_base = link_parent_dir.startswith(self._local_path) and link_parent_dir != self._local_path
                    will_create_parent = False
                    if is_parent_relative_to_base:
                        # 检查这个父目录是否是待创建项目的一部分
                        parent_rel_path_for_check = os.path.relpath(link_parent_dir, self._local_path) + '/'
                        if parent_rel_path_for_check in items_to_create_locally:
                            will_create_parent = True
                    if not will_create_parent and is_parent_relative_to_base : # 只有当父目录不是由其他条目创建时才单独提示
                        logger.info(f"  DRY RUN: (如果不存在，将创建父目录: {link_parent_dir})")

        if self._dry_run:
            logger.info("\n！！！DRY RUN 结束。没有实际更改文件系统。！！！")
        logger.info("\n同步过程结束。")


    def stop_service(self):
        """
        退出插件
        """
        pass
