import os
import json
from typing import Optional, Dict, Any, List
from openai import OpenAI
from flask import current_app
from app.services.preset_service import PresetService


class LLMService:
    """大模型对话服务 - Agent模式"""
    
    _instance = None
    _history: List[Dict[str, str]] = []
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._history = []
            cls._instance._preset_service = None
        return cls._instance
    
    def _get_preset_service(self) -> PresetService:
        """获取预设服务（延迟初始化）"""
        if self._preset_service is None:
            self._preset_service = PresetService()
        return self._preset_service
    
    def _get_client(self) -> OpenAI:
        """获取OpenAI客户端"""
        api_key = os.getenv('LLM_API_KEY') or current_app.config.get('LLM_API_KEY')
        base_url = os.getenv('LLM_BASE_URL') or current_app.config.get('LLM_BASE_URL')
        
        if not api_key:
            raise ValueError("请配置 LLM_API_KEY")
        
        return OpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    def _get_model(self) -> str:
        """获取模型名称"""
        return os.getenv('LLM_MODEL') or current_app.config.get('LLM_MODEL', 'gpt-4o')
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词 - Agent模式"""
        return """你是一个Android手机自动化助手。根据用户指令和当前屏幕状态，一步一步完成任务。

重要规则：
1. 每次只返回一个操作
2. 优先使用OCR识别的文字信息来定位元素，OCR结果包含文字内容和精确的中心点坐标，可直接用于点击
3. UI布局信息作为辅助，bounds属性格式为[left,top][right,bottom]，点击时使用中心坐标
4. 执行完一步后会收到新的屏幕状态，再决定下一步
5. 任务完成返回 {"status": "completed", "message": "说明"}
6. 无法继续返回 {"status": "failed", "message": "原因"}
7. 需要操作返回 {"status": "action", "action": {...}, "message": "说明"}

滑动查找规则（重要）：
- 如果上一步操作结果提示"页面已到达底部/顶部"，说明继续同方向滑动无效
- 此时应该改变滑动方向：到底部后向下滑动（回到顶部），到顶部后向上滑动（向底部）
- 如果两个方向都滑动过了还是找不到目标，考虑目标可能不在当前页面

可用操作：
- 点击: {"type": "click", "params": {"x": 540, "y": 1200}}
  （优先使用OCR结果中的center坐标，或从bounds计算：x=(left+right)/2, y=(top+bottom)/2）
- 滑动: {"type": "swipe", "params": {"direction": "up/down/left/right"}}
  （up=向上滑动查看下方内容, down=向下滑动查看上方内容）
- 输入: {"type": "input", "params": {"text": "文本"}}
- 按键: {"type": "press", "params": {"key": "back/home/enter"}}
- 等待: {"type": "wait", "params": {"seconds": 2}}
- 启动应用: {"type": "start_app", "params": {"package": "com.xxx.xxx"}}

严格按JSON格式返回，无其他内容：
{"status": "action/completed/failed", "action": {...}, "message": "说明"}
"""
    
    def analyze_and_act(
        self,
        task: str,
        screenshot: Optional[str] = None,
        ui_hierarchy: Optional[str] = None,
        current_app: Optional[Dict[str, str]] = None,
        previous_action: Optional[str] = None,
        ocr_result: Optional[Dict[str, Any]] = None,
        previous_app_package: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析当前屏幕并决定下一步操作
        
        Args:
            task: 用户任务描述
            screenshot: Base64编码的截图（可选，用于视觉模型）
            ui_hierarchy: UI层级XML（可选）
            current_app: 当前应用信息
            previous_action: 上一步操作结果
            ocr_result: OCR识别结果，包含文字和坐标信息
            previous_app_package: 上一步的APP包名（用于检测APP切换）
        """
        client = self._get_client()
        model = self._get_model()
        
        # 构建用户消息
        user_message = f"用户任务: {task}\n"
        
        # 获取当前APP包名
        current_package = current_app.get('package', '') if current_app else ''
        
        # 根据当前APP获取预设列表（首次或APP切换时）
        preset_info = ""
        preset_service = self._get_preset_service()
        
        # 判断是否需要发送预设（首次调用或APP切换）
        should_send_presets = (
            previous_action is None or  # 第一步
            previous_app_package != current_package  # APP切换了
        )
        
        if should_send_presets and current_package:
            preset_info = preset_service.format_app_presets_for_ai(current_package, task)
            if preset_info:
                user_message += f"\n{preset_info}\n"
        
        if current_app:
            package = current_app.get('package', '未知')
            activity = current_app.get('activity', '')
            app_name = preset_service.get_app_name(package)
            user_message += f"\n当前应用: {app_name} ({package})"
            if activity:
                user_message += f"\nActivity: {activity}"
            user_message += "\n"
        
        if previous_action:
            user_message += f"\n上一步操作: {previous_action}\n"
        
        # 优先添加OCR识别结果（更精确的文字和坐标信息）
        if ocr_result and ocr_result.get('elements'):
            ocr_summary = self._summarize_ocr(ocr_result)
            user_message += f"\n【OCR识别的屏幕文字（含精确坐标）】:\n{ocr_summary}\n"
        
        if ui_hierarchy:
            # 提取关键UI信息
            ui_summary = self._summarize_ui(ui_hierarchy)
            user_message += f"\n【UI布局元素】:\n{ui_summary}\n"
        
        user_message += "\n请分析当前屏幕，决定下一步操作。优先使用OCR结果中的坐标进行点击。只返回JSON格式。"
        
        # 构建消息
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        
        # 添加图片（如果支持视觉模型）
        if screenshot and ('gpt-4' in model or 'vision' in model.lower() or 'qwen-vl' in model.lower() or 'glm-4v' in model.lower()):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_message},
                    {"type": "image_url", "image_url": {"url": screenshot}}
                ]
            })
        else:
            messages.append({"role": "user", "content": user_message})
        
        # 调用API
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1000,
            temperature=0.3
        )
        
        assistant_message = response.choices[0].message.content
        
        # 解析响应
        result = self._parse_response(assistant_message)
        
        # 添加调试信息
        result['debug'] = {
            'model': model,
            'user_message': user_message,
            'raw_response': assistant_message,
            'has_screenshot': screenshot is not None,
            'has_ui_hierarchy': ui_hierarchy is not None,
            'has_preset': bool(preset_info)
        }
        
        return result
    
    def _summarize_ocr(self, ocr_result: Dict[str, Any], max_elements: int = 50) -> str:
        """
        格式化OCR识别结果，供AI分析使用
        
        Args:
            ocr_result: OCR识别结果字典
            max_elements: 最大元素数量
            
        Returns:
            格式化的OCR文字信息
        """
        if not ocr_result or ocr_result.get('error'):
            return "OCR识别失败或无结果"
        
        elements = ocr_result.get('elements', [])
        if not elements:
            return "屏幕上未识别到文字"
        
        # 按从上到下、从左到右排序
        elements = sorted(elements, key=lambda x: (x['bounds']['top'], x['bounds']['left']))
        
        # 限制数量
        if len(elements) > max_elements:
            elements = elements[:max_elements]
        
        lines = []
        for i, elem in enumerate(elements, 1):
            # 格式: 序号. "文字" -> 点击坐标(x, y)
            text = elem['text']
            center = elem['center']
            confidence = elem.get('confidence', 0)
            
            # 只显示置信度较高的结果
            if confidence >= 0.5:
                lines.append(f'{i}. "{text}" -> 点击坐标({center[0]}, {center[1]})')
        
        if not lines:
            return "屏幕上未识别到高置信度的文字"
        
        return '\n'.join(lines)
    
    def _summarize_ui(self, ui_hierarchy: str, max_length: int = 3000) -> str:
        """
        提取UI层级中的关键信息
        """
        import xml.etree.ElementTree as ET
        
        try:
            root = ET.fromstring(ui_hierarchy)
            elements = []
            
            def extract_elements(node, depth=0):
                attribs = node.attrib
                text = attribs.get('text', '').strip()
                desc = attribs.get('content-desc', '').strip()
                resource_id = attribs.get('resource-id', '').strip()
                clickable = attribs.get('clickable', 'false') == 'true'
                bounds = attribs.get('bounds', '')
                class_name = attribs.get('class', '').split('.')[-1]
                
                # 只提取有意义的元素
                if text or desc or (clickable and resource_id):
                    info_parts = []
                    if text:
                        info_parts.append(f'text="{text}"')
                    if desc:
                        info_parts.append(f'desc="{desc}"')
                    if resource_id:
                        short_id = resource_id.split('/')[-1] if '/' in resource_id else resource_id
                        info_parts.append(f'id="{short_id}"')
                    if clickable:
                        info_parts.append('clickable')
                    if bounds:
                        info_parts.append(f'bounds={bounds}')
                    
                    elements.append(f"[{class_name}] {' '.join(info_parts)}")
                
                for child in node:
                    extract_elements(child, depth + 1)
            
            extract_elements(root)
            
            result = '\n'.join(elements[:80])  # 增加元素数量限制
            if len(result) > max_length:
                result = result[:max_length] + '...'
            
            return result
            
        except Exception as e:
            return ui_hierarchy[:max_length] + '...' if len(ui_hierarchy) > max_length else ui_hierarchy
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """
        解析AI响应
        """
        try:
            response = response.strip()
            
            # 移除可能的markdown代码块标记
            if response.startswith('```'):
                lines = response.split('\n')
                response = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
                response = response.strip()
            
            result = json.loads(response)
            
            if 'status' not in result:
                result['status'] = 'action' if 'action' in result else 'failed'
            if 'message' not in result:
                result['message'] = ''
            
            return result
            
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    if 'status' not in result:
                        result['status'] = 'action' if 'action' in result else 'failed'
                    if 'message' not in result:
                        result['message'] = ''
                    return result
                except:
                    pass
            
            return {
                'status': 'failed',
                'message': f'无法解析AI响应: {response[:200]}'
            }
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self._history.copy()
    
    def clear_history(self):
        """清空对话历史"""
        self._history.clear()
