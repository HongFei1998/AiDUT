import time
from typing import Dict, Any, Generator, List, Optional
from app.services.device_service import DeviceService
from app.services.llm_service import LLMService
from app.services.ocr_service import ocr_service


class AgentService:
    """
    Agent服务 - 自动循环执行任务
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._stop_flag = False
            cls._instance._ocr_service = None
        return cls._instance
    
    def __init__(self):
        self.device_service = DeviceService()
        self.llm_service = LLMService()
        self.max_steps = 20
        self.action_delay = 1.0
        self._stop_flag = getattr(self, '_stop_flag', False)
        # 延迟初始化 OCR 服务（首次使用时初始化，避免启动时加载模型）
        if not hasattr(self, '_ocr_service') or self._ocr_service is None:
            self._ocr_service = None
        
        # 滑动检测相关状态
        self._last_ocr_texts: Optional[set] = None  # 上一次的OCR文字集合
        self._last_swipe_direction: Optional[str] = None  # 上一次滑动方向
        self._same_content_swipe_count: int = 0  # 连续滑动内容不变的次数
        self._page_boundary_info: Optional[str] = None  # 页面边界信息
    
    def stop(self):
        """停止当前执行"""
        self._stop_flag = True
    
    def reset_stop_flag(self):
        """重置停止标志"""
        self._stop_flag = False
    
    def is_stopped(self) -> bool:
        """检查是否已停止"""
        return self._stop_flag
    
    def _reset_swipe_detection(self):
        """重置滑动检测状态"""
        self._last_ocr_texts = None
        self._last_swipe_direction = None
        self._same_content_swipe_count = 0
        self._page_boundary_info = None
    
    def _extract_ocr_texts(self, ocr_result: Dict[str, Any]) -> set:
        """从OCR结果中提取文字集合"""
        if not ocr_result or ocr_result.get('error'):
            return set()
        elements = ocr_result.get('elements', [])
        return set(elem['text'] for elem in elements if elem.get('text'))
    
    def _calculate_content_similarity(self, texts1: set, texts2: set) -> float:
        """
        计算两个文字集合的相似度 (Jaccard相似度)
        返回 0-1 之间的值，1表示完全相同
        """
        if not texts1 and not texts2:
            return 1.0
        if not texts1 or not texts2:
            return 0.0
        
        intersection = len(texts1 & texts2)
        union = len(texts1 | texts2)
        return intersection / union if union > 0 else 0.0
    
    def _detect_page_boundary(self, current_ocr: Dict[str, Any], last_action: Dict[str, Any]) -> str:
        """
        检测是否到达页面边界
        
        Args:
            current_ocr: 当前OCR结果
            last_action: 上一次执行的操作
            
        Returns:
            边界信息字符串，如果没有到边界则返回空字符串
        """
        # 只对滑动操作进行检测
        if not last_action or last_action.get('type') != 'swipe':
            self._reset_swipe_detection()
            return ""
        
        params = last_action.get('params', {})
        current_direction = params.get('direction', '')
        
        if not current_direction:
            return ""
        
        # 提取当前OCR文字
        current_texts = self._extract_ocr_texts(current_ocr)
        
        # 如果有上一次的OCR记录，计算相似度
        if self._last_ocr_texts is not None:
            similarity = self._calculate_content_similarity(self._last_ocr_texts, current_texts)
            
            # 如果相似度超过90%，说明内容几乎没变化
            if similarity > 0.9:
                # 同方向滑动
                if current_direction == self._last_swipe_direction:
                    self._same_content_swipe_count += 1
                else:
                    self._same_content_swipe_count = 1
                
                # 连续2次同方向滑动内容不变，判断为到达边界
                if self._same_content_swipe_count >= 2:
                    if current_direction == 'up':
                        self._page_boundary_info = "【注意】页面已经到达底部，继续向上滑动无效。如需查找更多内容，请尝试向下滑动（回到顶部方向）。"
                    elif current_direction == 'down':
                        self._page_boundary_info = "【注意】页面已经到达顶部，继续向下滑动无效。如需查找更多内容，请尝试向上滑动（向底部方向）。"
                    elif current_direction == 'left':
                        self._page_boundary_info = "【注意】页面已经到达最右侧，继续向左滑动无效。请尝试向右滑动。"
                    elif current_direction == 'right':
                        self._page_boundary_info = "【注意】页面已经到达最左侧，继续向右滑动无效。请尝试向左滑动。"
            else:
                # 内容有变化，重置计数
                self._same_content_swipe_count = 0
                self._page_boundary_info = None
        
        # 更新记录
        self._last_ocr_texts = current_texts
        self._last_swipe_direction = current_direction
        
        return self._page_boundary_info or ""
    
    def _get_ocr_service(self) -> ocr_service:
        """获取 OCR 服务（延迟初始化）"""
        if self._ocr_service is None:
            self._ocr_service = ocr_service()
        return self._ocr_service
    
    def _get_screen_state(self) -> tuple:
        """获取当前屏幕状态，包含 OCR 识别结果"""
        screenshot = self.device_service.get_screenshot()
        ui_hierarchy = self.device_service.dump_hierarchy()
        current_app = self.device_service.get_current_app()
        
        # 获取 OCR 识别结果
        ocr_result = None
        try:
            # 保存截图到临时文件用于 OCR
            screenshot_file = self.device_service.get_screenshot_file()
            ocr_svc = self._get_ocr_service()
            ocr_result = ocr_svc.get_all_text_with_positions(screenshot_file)
        except Exception as e:
            print(f"OCR识别失败: {e}")
            ocr_result = {"error": str(e), "elements": []}
        
        return screenshot, ui_hierarchy, current_app, ocr_result
    
    def execute_task(self, task: str) -> Generator[Dict[str, Any], None, None]:
        """执行任务"""
        self.reset_stop_flag()
        self._reset_swipe_detection()  # 重置滑动检测状态
        
        if not self.device_service.is_connected():
            yield {'type': 'error', 'message': '设备未连接，请先连接设备'}
            return
        
        yield {'type': 'start', 'message': f'🚀 开始执行: {task}'}
        
        # 获取初始屏幕状态
        try:
            current_screenshot, current_ui_hierarchy, current_app, current_ocr = self._get_screen_state()
            ocr_count = len(current_ocr.get('elements', [])) if current_ocr else 0
            yield {
                'type': 'info',
                'message': f'📱 当前应用: {current_app.get("package", "未知")} | OCR识别: {ocr_count}个文字',
                'screenshot': current_screenshot
            }
            # 初始化OCR文字记录
            self._last_ocr_texts = self._extract_ocr_texts(current_ocr)
        except Exception as e:
            yield {'type': 'error', 'message': f'获取屏幕状态失败: {str(e)}'}
            return
        
        step = 0
        previous_action_result = None
        last_action = None  # 记录上一次执行的操作
        previous_app_package = None  # 记录上一步的APP包名，用于检测APP切换
        
        while step < self.max_steps:
            if self.is_stopped():
                yield {'type': 'stopped', 'message': '⏹️ 任务已停止'}
                return
            
            step += 1
            
            # AI分析
            yield {'type': 'thinking', 'message': f'🤔 正在分析...'}
            
            try:
                result = self.llm_service.analyze_and_act(
                    task=task,
                    screenshot=current_screenshot,
                    ui_hierarchy=current_ui_hierarchy,
                    current_app=current_app,
                    previous_action=previous_action_result,
                    ocr_result=current_ocr,
                    previous_app_package=previous_app_package  # 传递上一步的APP包名
                )
            except Exception as e:
                yield {'type': 'error', 'message': f'❌ AI分析失败: {str(e)}'}
                return
            
            # 更新上一步的APP包名
            previous_app_package = current_app.get('package', '') if current_app else None
            
            status = result.get('status', 'failed')
            message = result.get('message', '')
            action = result.get('action')
            debug = result.get('debug', {})
            
            if status == 'completed':
                yield {'type': 'completed', 'message': f'✅ {message}', 'debug': debug}
                return
            
            elif status == 'failed':
                yield {'type': 'failed', 'message': f'❌ {message}', 'debug': debug}
                return
            
            elif status == 'action' and action:
                yield {
                    'type': 'action',
                    'message': f'▶️ 步骤{step}: {message}',
                    'action': action,
                    'debug': debug
                }
                
                if self.is_stopped():
                    yield {'type': 'stopped', 'message': '⏹️ 任务已停止'}
                    return
                
                # 执行操作
                try:
                    action_result = self._execute_action(action)
                    previous_action_result = f"{message} -> {action_result}"
                    last_action = action  # 记录执行的操作
                    yield {'type': 'done', 'message': f'✓ {action_result}'}
                except Exception as e:
                    previous_action_result = f"{message} -> 失败: {str(e)}"
                    last_action = None
                    yield {'type': 'warning', 'message': f'⚠️ {str(e)}'}
                
                # 等待并获取新状态
                time.sleep(self.action_delay)
                
                try:
                    current_screenshot, current_ui_hierarchy, current_app, current_ocr = self._get_screen_state()
                    ocr_count = len(current_ocr.get('elements', [])) if current_ocr else 0
                    
                    # 检测页面边界（滑动后内容是否变化）
                    boundary_info = self._detect_page_boundary(current_ocr, last_action)
                    if boundary_info:
                        previous_action_result += f"\n{boundary_info}"
                        yield {'type': 'warning', 'message': f'⚠️ 检测到页面边界，内容无变化'}
                    
                    yield {
                        'type': 'update',
                        'message': f'📱 当前: {current_app.get("package", "").split(".")[-1] or "未知"} | OCR: {ocr_count}个',
                        'screenshot': current_screenshot
                    }
                except Exception as e:
                    yield {'type': 'warning', 'message': f'⚠️ 获取屏幕失败，继续'}
            else:
                yield {'type': 'error', 'message': f'❌ 无效响应'}
                return
        
        yield {'type': 'warning', 'message': f'⏱️ 已达最大步数({self.max_steps}步)'}
    
    def _execute_action(self, action: Dict[str, Any]) -> str:
        """执行单个操作"""
        action_type = action.get('type')
        params = action.get('params', {})
        
        if action_type == 'click':
            x, y = params.get('x'), params.get('y')
            self.device_service.click(x, y)
            return f'点击({x},{y})'
        
        elif action_type == 'swipe':
            if 'direction' in params:
                self.device_service.swipe_ext(params['direction'])
                return f'向{params["direction"]}滑动'
            else:
                self.device_service.swipe(
                    params.get('start_x'), params.get('start_y'),
                    params.get('end_x'), params.get('end_y'),
                    params.get('duration', 0.5)
                )
                return '滑动'
        
        elif action_type == 'input':
            text = params.get('text', '')
            self.device_service.send_keys(text)
            return f'输入"{text}"'
        
        elif action_type == 'press':
            key = params.get('key', 'back')
            self.device_service.press(key)
            return f'按{key}'
        
        elif action_type == 'wait':
            seconds = params.get('seconds', 1)
            time.sleep(seconds)
            return f'等待{seconds}秒'
        
        elif action_type == 'start_app':
            package = params.get('package')
            if not package:
                raise Exception('缺少包名')
            self.device_service.app_start(package)
            return f'启动{package}'
        
        else:
            raise Exception(f'未知操作: {action_type}')
    
    def execute_single_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个操作"""
        try:
            result = self._execute_action(action)
            return {'success': True, 'message': result}
        except Exception as e:
            return {'success': False, 'message': str(e)}
