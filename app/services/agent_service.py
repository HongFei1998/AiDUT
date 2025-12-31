import time
import concurrent.futures
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
        self.max_steps = 50
        self.action_delay = 0.8  # 减少等待时间（原来是1.0）
        self._stop_flag = getattr(self, '_stop_flag', False)
        
        # 性能优化选项
        self.skip_ui_hierarchy = False  # 是否跳过 UI 层级（可大幅加速，但可能影响准确性）
        self.parallel_enabled = True    # 是否启用并行获取
        
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
    
    def _get_screen_state(self, skip_ui_hierarchy: bool = False) -> tuple:
        """
        获取当前屏幕状态，包含 OCR 识别结果和耗时统计
        使用并行执行优化性能
        
        Args:
            skip_ui_hierarchy: 是否跳过 UI 层级获取（可加速约 500-1500ms）
        
        Returns:
            (screenshot, ui_hierarchy, current_app, ocr_result, timing)
        """
        timing = {}
        total_start = time.time()
        
        # 使用线程池并行执行
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # 提交并行任务
            # 任务1: 截图 + 保存 + OCR（串行，因为 OCR 依赖截图）
            def screenshot_and_ocr():
                result = {'screenshot': None, 'ocr': None, 'timing': {}}
                
                # 截图
                t0 = time.time()
                result['screenshot'] = self.device_service.get_screenshot()
                result['timing']['screenshot'] = round((time.time() - t0) * 1000)
                
                # 保存截图供 OCR 使用
                t0 = time.time()
                screenshot_file = self.device_service.get_screenshot_file()
                result['timing']['save_screenshot'] = round((time.time() - t0) * 1000)
                
                # OCR 识别
                t0 = time.time()
                try:
                    ocr_svc = self._get_ocr_service()
                    result['ocr'] = ocr_svc.get_all_text_with_positions(screenshot_file)
                except Exception as e:
                    print(f"OCR识别失败: {e}")
                    result['ocr'] = {"error": str(e), "elements": []}
                result['timing']['ocr'] = round((time.time() - t0) * 1000)
                
                return result
            
            # 任务2: UI 层级（可选）
            def get_ui_hierarchy():
                if skip_ui_hierarchy:
                    return {'hierarchy': '', 'time': 0}
                t0 = time.time()
                hierarchy = self.device_service.dump_hierarchy()
                return {'hierarchy': hierarchy, 'time': round((time.time() - t0) * 1000)}
            
            # 任务3: 当前应用信息
            def get_current_app():
                t0 = time.time()
                app = self.device_service.get_current_app()
                return {'app': app, 'time': round((time.time() - t0) * 1000)}
            
            # 并行提交任务
            future_screenshot_ocr = executor.submit(screenshot_and_ocr)
            future_ui = executor.submit(get_ui_hierarchy)
            future_app = executor.submit(get_current_app)
            
            # 等待所有任务完成并收集结果
            screenshot_ocr_result = future_screenshot_ocr.result()
            ui_result = future_ui.result()
            app_result = future_app.result()
        
        # 汇总结果
        screenshot = screenshot_ocr_result['screenshot']
        ocr_result = screenshot_ocr_result['ocr']
        ui_hierarchy = ui_result['hierarchy']
        current_app = app_result['app']
        
        # 汇总耗时
        timing.update(screenshot_ocr_result['timing'])
        timing['ui_hierarchy'] = ui_result['time']
        timing['current_app'] = app_result['time']
        
        # 计算总耗时（并行执行后的实际耗时）
        timing['total'] = round((time.time() - total_start) * 1000)
        
        # 计算节省的时间（串行耗时 - 并行耗时）
        serial_time = sum(v for k, v in timing.items() if k != 'total')
        timing['saved'] = serial_time - timing['total']
        
        return screenshot, ui_hierarchy, current_app, ocr_result, timing
    
    def _format_timing(self, timing: Dict[str, int], verbose: bool = True) -> str:
        """格式化耗时统计信息"""
        parts = []
        
        # 显示所有主要耗时项
        if 'screenshot' in timing:
            parts.append(f"截图:{timing['screenshot']}ms")
        if 'save_screenshot' in timing and timing['save_screenshot'] > 0:
            parts.append(f"保存:{timing['save_screenshot']}ms")
        if 'ui_hierarchy' in timing and timing['ui_hierarchy'] > 0:
            parts.append(f"布局:{timing['ui_hierarchy']}ms")
        if 'ocr' in timing:
            parts.append(f"OCR:{timing['ocr']}ms")
        if 'current_app' in timing and timing['current_app'] > 0:
            parts.append(f"应用:{timing['current_app']}ms")
        
        # 串行总耗时（各步骤相加）
        serial_time = sum(v for k, v in timing.items() if k not in ['total', 'saved'])
        
        # 并行实际耗时
        total = timing.get('total', 0)
        
        # 显示对比
        parts.append(f"串行:{serial_time}ms")
        parts.append(f"并行:{total}ms")
        
        # 显示节省的时间
        saved = timing.get('saved', 0)
        if saved > 0:
            parts.append(f"省:{saved}ms")
        
        return " | ".join(parts)
    
    def execute_task(self, task: str) -> Generator[Dict[str, Any], None, None]:
        """执行任务"""
        self.reset_stop_flag()
        self._reset_swipe_detection()  # 重置滑动检测状态
        
        if not self.device_service.is_connected():
            yield {'type': 'error', 'message': '设备未连接，请先连接设备'}
            return
        
        task_start_time = time.time()  # 任务开始时间
        yield {'type': 'start', 'message': f'🚀 开始执行: {task}'}
        
        # 获取初始屏幕状态
        try:
            current_screenshot, current_ui_hierarchy, current_app, current_ocr, init_timing = self._get_screen_state(
                skip_ui_hierarchy=self.skip_ui_hierarchy
            )
            ocr_count = len(current_ocr.get('elements', [])) if current_ocr else 0
            timing_str = self._format_timing(init_timing)
            yield {
                'type': 'info',
                'message': f'📱 当前应用: {current_app.get("package", "未知")} | OCR: {ocr_count}个 | ⏱️ {timing_str}',
                'screenshot': current_screenshot,
                'timing': init_timing
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
        action_history = []  # 操作历史记录
        memories = []  # AI 记录的关键信息（如短信内容、查询结果等）
        
        while step < self.max_steps:
            if self.is_stopped():
                task_duration = round(time.time() - task_start_time, 1)
                yield {'type': 'stopped', 'message': f'⏹️ 任务已停止 | 总耗时: {task_duration}秒 | 执行了{step}步'}
                return
            
            step += 1
            
            # AI分析
            yield {'type': 'thinking', 'message': f'🤔 步骤{step} 正在分析...'}
            
            ai_start = time.time()
            try:
                result = self.llm_service.analyze_and_act(
                    task=task,
                    screenshot=current_screenshot,
                    ui_hierarchy=current_ui_hierarchy,
                    current_app=current_app,
                    previous_action=previous_action_result,
                    ocr_result=current_ocr,
                    previous_app_package=previous_app_package,  # 传递上一步的APP包名
                    step_number=step,
                    action_history=action_history,  # 传递操作历史
                    memories=memories  # 传递记忆信息
                )
                ai_time = round((time.time() - ai_start) * 1000)  # AI耗时(毫秒)
            except Exception as e:
                yield {'type': 'error', 'message': f'❌ AI分析失败: {str(e)}'}
                return
            
            # 更新上一步的APP包名
            previous_app_package = current_app.get('package', '') if current_app else None
            
            status = result.get('status', 'failed')
            message = result.get('message', '')
            action = result.get('action')
            debug = result.get('debug', {})
            memory = result.get('memory')  # AI 记录的关键信息
            
            # 如果 AI 记录了新的记忆，保存下来
            if memory:
                memories.append(memory)
                yield {'type': 'info', 'message': f'📝 记录: {memory}'}
            
            # 添加 AI 耗时到 debug 信息
            debug['ai_time_ms'] = ai_time
            debug['memories'] = memories.copy()  # 添加当前记忆到 debug
            
            if status == 'completed':
                task_duration = round(time.time() - task_start_time, 1)
                # 如果有记忆，在完成消息中包含
                complete_msg = f'✅ {message}'
                if memories:
                    complete_msg += f'\n📋 记录的信息: {"; ".join(memories)}'
                complete_msg += f'\n⏱️ 总耗时: {task_duration}秒 | 共{step}步 | 本步AI:{ai_time}ms'
                yield {'type': 'completed', 'message': complete_msg, 'debug': debug}
                return
            
            elif status == 'failed':
                task_duration = round(time.time() - task_start_time, 1)
                yield {'type': 'failed', 'message': f'❌ {message}\n⏱️ 总耗时: {task_duration}秒 | 共{step}步', 'debug': debug}
                return
            
            elif status == 'action' and action:
                yield {
                    'type': 'action',
                    'message': f'▶️ 步骤{step}: {message} (AI:{ai_time}ms)',
                    'action': action,
                    'debug': debug
                }
                
                if self.is_stopped():
                    task_duration = round(time.time() - task_start_time, 1)
                    yield {'type': 'stopped', 'message': f'⏹️ 任务已停止 | 总耗时: {task_duration}秒 | 执行了{step}步'}
                    return
                
                # 执行操作
                action_start = time.time()
                try:
                    action_result = self._execute_action(action)
                    action_time = round((time.time() - action_start) * 1000)
                    previous_action_result = f"{message} -> {action_result}"
                    last_action = action  # 记录执行的操作
                    # 记录到操作历史
                    action_history.append(f"{message} ({action_result})")
                    yield {'type': 'done', 'message': f'✓ {action_result} ({action_time}ms)'}
                except Exception as e:
                    action_time = round((time.time() - action_start) * 1000)
                    previous_action_result = f"{message} -> 失败: {str(e)}"
                    last_action = None
                    action_history.append(f"{message} (失败: {str(e)})")
                    yield {'type': 'warning', 'message': f'⚠️ {str(e)} ({action_time}ms)'}
                
                # 等待并获取新状态
                time.sleep(self.action_delay)
                
                try:
                    current_screenshot, current_ui_hierarchy, current_app, current_ocr, step_timing = self._get_screen_state(
                        skip_ui_hierarchy=self.skip_ui_hierarchy
                    )
                    ocr_count = len(current_ocr.get('elements', [])) if current_ocr else 0
                    
                    # 检测页面边界（滑动后内容是否变化）
                    boundary_info = self._detect_page_boundary(current_ocr, last_action)
                    if boundary_info:
                        previous_action_result += f"\n{boundary_info}"
                        yield {'type': 'warning', 'message': f'⚠️ 检测到页面边界，内容无变化'}
                    
                    # 格式化耗时
                    timing_str = self._format_timing(step_timing)
                    yield {
                        'type': 'update',
                        'message': f'📱 当前: {current_app.get("package", "").split(".")[-1] or "未知"} | OCR: {ocr_count}个 | ⏱️ {timing_str}',
                        'screenshot': current_screenshot,
                        'timing': step_timing
                    }
                except Exception as e:
                    yield {'type': 'warning', 'message': f'⚠️ 获取屏幕失败，继续'}
            else:
                task_duration = round(time.time() - task_start_time, 1)
                yield {'type': 'error', 'message': f'❌ 无效响应 | 总耗时: {task_duration}秒 | 执行了{step}步'}
                return
        
        task_duration = round(time.time() - task_start_time, 1)
        yield {'type': 'warning', 'message': f'⏱️ 已达最大步数({self.max_steps}步) | 总耗时: {task_duration}秒'}
    
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
