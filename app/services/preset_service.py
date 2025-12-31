import os
import json
import re
from typing import Dict, Any, List, Optional


class PresetService:
    """预设操作流程服务 - 按APP组织"""
    
    _instance = None
    _presets: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_presets()
        return cls._instance
    
    def _load_presets(self):
        """加载预设配置文件"""
        preset_file = os.path.join(os.path.dirname(__file__), 'presets.json')
        try:
            if os.path.exists(preset_file):
                with open(preset_file, 'r', encoding='utf-8') as f:
                    self._presets = json.load(f)
                app_count = len(self._presets)
                preset_count = sum(len(app.get('presets', {})) for app in self._presets.values())
                print(f"已加载 {app_count} 个APP的 {preset_count} 个预设流程")
            else:
                self._presets = {}
                print("预设配置文件不存在")
        except Exception as e:
            print(f"加载预设配置失败: {e}")
            self._presets = {}
    
    def reload_presets(self):
        """重新加载预设配置"""
        self._load_presets()
    
    def get_app_presets(self, package_name: str) -> Optional[Dict[str, Any]]:
        """
        根据APP包名获取该APP的所有预设
        
        Args:
            package_name: APP包名
            
        Returns:
            该APP的预设信息，如果没有则返回None
        """
        return self._presets.get(package_name)
    
    def get_app_name(self, package_name: str) -> str:
        """获取APP名称"""
        app_info = self._presets.get(package_name, {})
        return app_info.get('app_name', package_name.split('.')[-1])
    
    def format_app_presets_for_ai(self, package_name: str, task: str = "") -> str:
        """
        格式化某个APP的所有预设，发送给AI参考
        
        Args:
            package_name: 当前APP包名
            task: 用户任务（可选，用于高亮匹配的预设）
            
        Returns:
            格式化的预设列表
        """
        app_info = self._presets.get(package_name)
        
        if not app_info:
            return ""
        
        app_name = app_info.get('app_name', package_name)
        presets = app_info.get('presets', {})
        
        if not presets:
            return ""
        
        # 找出与任务最匹配的预设（如果有）
        best_match_name = self._find_best_match(presets, task) if task else None
        
        lines = [f"【{app_name} 常用操作参考】"]
        
        for preset_name, preset_info in presets.items():
            # 如果是最佳匹配，添加推荐标记
            if preset_name == best_match_name:
                lines.append(f"\n★ {preset_name}（推荐）:")
            else:
                lines.append(f"\n• {preset_name}:")
            
            steps = preset_info.get('steps', [])
            for i, step in enumerate(steps, 1):
                lines.append(f"    {i}. {step}")
        
        lines.append("\n（以上仅供参考，请根据实际屏幕内容灵活执行）")
        
        return '\n'.join(lines)
    
    def _find_best_match(self, presets: Dict[str, Any], task: str) -> Optional[str]:
        """
        在给定的预设中找出与任务最匹配的
        
        Args:
            presets: 预设字典
            task: 用户任务
            
        Returns:
            最匹配的预设名称
        """
        if not task:
            return None
        
        task_lower = task.lower()
        best_name = None
        best_score = 0
        
        for preset_name, preset_info in presets.items():
            score = 0
            keywords = preset_info.get('keywords', [])
            
            # 关键词匹配
            for keyword in keywords:
                if keyword.lower() in task_lower:
                    score += len(keyword)
            
            # 预设名称匹配
            if preset_name.lower() in task_lower:
                score += len(preset_name)
            
            if score > best_score:
                best_score = score
                best_name = preset_name
        
        # 只有达到一定分数才返回
        return best_name if best_score >= 2 else None
    
    def detect_target_app(self, task: str) -> Optional[str]:
        """
        从任务描述中识别目标APP
        
        Args:
            task: 用户任务描述
            
        Returns:
            APP包名，如果无法识别则返回None
        """
        task_lower = task.lower()
        
        # 从动态映射中查找
        mapping = self.get_app_package_mapping()
        
        for app_name, package in mapping.items():
            if app_name.lower() in task_lower:
                return package
        
        return None
    
    def should_update_presets(self, previous_app: str, current_app: str) -> bool:
        """
        判断是否需要更新预设（APP切换时）
        
        Args:
            previous_app: 上一个APP包名
            current_app: 当前APP包名
            
        Returns:
            是否需要更新预设
        """
        if not previous_app or not current_app:
            return True
        return previous_app != current_app
    
    def get_all_supported_apps(self) -> List[Dict[str, str]]:
        """获取所有支持预设的APP列表"""
        apps = []
        for package, info in self._presets.items():
            apps.append({
                'package': package,
                'name': info.get('app_name', package),
                'preset_count': len(info.get('presets', {}))
            })
        return apps
    
    def get_app_package_mapping(self) -> Dict[str, str]:
        """
        获取 APP 名称到包名的映射
        用于 AI 启动应用时查找包名
        
        Returns:
            {app_name: package_name} 映射字典
        """
        mapping = {}
        
        # 从预设配置中提取
        for package, info in self._presets.items():
            app_name = info.get('app_name', '')
            if app_name:
                mapping[app_name] = package
        
        # 补充常用 APP（可能不在预设中但常用）
        common_apps = {
            '设置': 'com.android.settings',
            '电话': 'com.android.dialer',
            '短信': 'com.android.mms',
            '相机': 'com.android.camera',
            '相册': 'com.android.gallery3d',
            '日历': 'com.android.calendar',
            '时钟': 'com.android.deskclock',
            '计算器': 'com.android.calculator2',
            '文件管理': 'com.android.fileexplorer',
            'QQ': 'com.tencent.mobileqq',
            '微博': 'com.sina.weibo',
            '网易云音乐': 'com.netease.cloudmusic',
            'QQ音乐': 'com.tencent.qqmusic',
            '酷狗音乐': 'com.kugou.android',
            '高德地图': 'com.autonavi.minimap',
            '百度地图': 'com.baidu.BaiduMap',
            '大众点评': 'com.dianping.v1',
            '饿了么': 'me.ele',
            '滴滴出行': 'com.sdu.didi.psnger',
            '哔哩哔哩': 'tv.danmaku.bili',
            'B站': 'tv.danmaku.bili',
            '小红书': 'com.xingin.xhs',
            '今日头条': 'com.ss.android.article.news',
            '钉钉': 'com.alibaba.android.rimet',
            '飞书': 'com.ss.android.lark',
            '腾讯会议': 'com.tencent.wemeet.app',
            '百度': 'com.baidu.searchbox',
            '知乎': 'com.zhihu.android',
            '拼多多': 'com.xunmeng.pinduoduo',
            '闲鱼': 'com.taobao.idlefish',
            '携程': 'ctrip.android.view',
            '去哪儿': 'com.Qunar',
            '优酷': 'com.youku.phone',
            '爱奇艺': 'com.qiyi.video',
            '腾讯视频': 'com.tencent.qqlive',
            '芒果TV': 'com.hunantv.imgo.activity',
            'UC浏览器': 'com.UCMobile',
            'Chrome': 'com.android.chrome',
            '快手': 'com.smile.gifmaker',
        }
        
        # 合并，预设中的优先
        for name, package in common_apps.items():
            if name not in mapping:
                mapping[name] = package
        
        return mapping
    
    def format_app_packages_for_ai(self) -> str:
        """
        格式化 APP 包名列表，供 AI 启动应用时参考
        
        Returns:
            格式化的 APP 包名列表字符串
        """
        mapping = self.get_app_package_mapping()
        
        lines = []
        for app_name, package in sorted(mapping.items(), key=lambda x: x[0]):
            lines.append(f"  {app_name}: {package}")
        
        return '\n'.join(lines)