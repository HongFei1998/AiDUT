import uiautomator2 as u2
import base64
import os
import tempfile
import subprocess
from io import BytesIO
from typing import Optional, Dict, Any, Union, List
import xml.etree.ElementTree as ET


class DeviceService:
    """设备控制服务 - 基于 uiautomator2 3.5.0"""
    
    _instance = None
    _device: Optional[u2.Device] = None
    
    def __new__(cls):
        """单例模式，确保只有一个设备连接"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    def list_devices() -> List[Dict[str, str]]:
        """
        获取已连接的 ADB 设备列表
        
        Returns:
            设备列表，每个设备包含 serial 和 status
        """
        devices = []
        try:
            result = subprocess.run(
                ['adb', 'devices'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split('\n')
            # 跳过第一行 "List of devices attached"
            for line in lines[1:]:
                line = line.strip()
                if line and '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        serial = parts[0].strip()
                        status = parts[1].strip()
                        # 只返回状态为 device 的设备
                        if status == 'device':
                            devices.append({
                                'serial': serial,
                                'status': status
                            })
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            # adb 命令未找到
            pass
        except Exception:
            pass
        
        return devices
    
    def connect(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        连接设备
        
        Args:
            serial: 设备序列号或IP地址，如果为None则自动连接第一个设备
            
        Returns:
            设备信息字典
        """
        if serial:
            self._device = u2.connect(serial)
        else:
            self._device = u2.connect()
        
        return self.get_device_info()
    
    def disconnect(self):
        """断开设备连接"""
        self._device = None
    
    def is_connected(self) -> bool:
        """检查设备是否已连接"""
        return self._device is not None
    
    def _ensure_connected(self):
        """确保设备已连接"""
        if not self.is_connected():
            raise Exception("设备未连接，请先连接设备")
    
    def get_device_info(self) -> Dict[str, Any]:
        """获取设备信息"""
        self._ensure_connected()
        
        # 使用 info 属性获取设备信息
        info = self._device.info
        # 使用 window_size() 获取屏幕尺寸
        window_size = self._device.window_size()
        # 使用 shell 获取更多设备信息
        serial = self._device.serial
        
        # 通过 shell 命令获取设备品牌和型号
        try:
            brand = self._device.shell("getprop ro.product.brand").output.strip()
            model = self._device.shell("getprop ro.product.model").output.strip()
            sdk = self._device.shell("getprop ro.build.version.sdk").output.strip()
            version = self._device.shell("getprop ro.build.version.release").output.strip()
        except Exception:
            brand = info.get('productName', '')
            model = ''
            sdk = str(info.get('sdkInt', ''))
            version = ''
        
        return {
            'serial': serial,
            'brand': brand,
            'model': model,
            'sdk': sdk,
            'version': version,
            'display': {
                'width': window_size[0],
                'height': window_size[1]
            }
        }
    
    def get_screenshot(self) -> str:
        """
        获取设备截图
        
        Returns:
            Base64编码的图片字符串
        """
        self._ensure_connected()
        
        # 获取截图 (返回 PIL.Image 对象)
        image = self._device.screenshot()
        
        # 转换为base64
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/png;base64,{img_base64}"
    
    def save_screenshot(self, filename: str):
        """保存截图到文件"""
        self._ensure_connected()
        self._device.screenshot(filename)
    
    def get_screenshot_file(self) -> str:
        """
        获取截图并保存到临时文件
        
        Returns:
            临时文件路径
        """
        self._ensure_connected()
        
        # 创建临时文件
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, 'aidut_screenshot.png')
        
        # 保存截图
        self._device.screenshot(temp_file)
        
        return temp_file
    
    def click(self, x: int, y: int):
        """
        点击指定坐标
        
        Args:
            x: X坐标
            y: Y坐标
        """
        self._ensure_connected()
        self._device.click(x, y)
    
    def double_click(self, x: int, y: int, duration: float = 0.1):
        """
        双击指定坐标
        
        Args:
            x: X坐标
            y: Y坐标
            duration: 两次点击之间的间隔（秒）
        """
        self._ensure_connected()
        self._device.double_click(x, y, duration)
    
    def long_click(self, x: int, y: int, duration: float = 0.5):
        """
        长按指定坐标
        
        Args:
            x: X坐标
            y: Y坐标
            duration: 长按时间（秒）
        """
        self._ensure_connected()
        self._device.long_click(x, y, duration)
    
    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        """
        滑动操作
        
        Args:
            start_x: 起始X坐标
            start_y: 起始Y坐标
            end_x: 结束X坐标
            end_y: 结束Y坐标
            duration: 滑动时间（秒）
        """
        self._ensure_connected()
        self._device.swipe(start_x, start_y, end_x, end_y, duration)
    
    def swipe_ext(self, direction: str, scale: float = 0.8, duration: float = 0.5):
        """
        扩展滑动操作
        
        Args:
            direction: 滑动方向 'up', 'down', 'left', 'right'
            scale: 滑动距离比例 (0-1)
            duration: 滑动时间（秒）
        """
        self._ensure_connected()
        self._device.swipe_ext(direction, scale=scale, duration=duration)
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5):
        """
        拖拽操作
        
        Args:
            start_x: 起始X坐标
            start_y: 起始Y坐标
            end_x: 结束X坐标
            end_y: 结束Y坐标
            duration: 拖拽时间（秒）
        """
        self._ensure_connected()
        self._device.drag(start_x, start_y, end_x, end_y, duration)
    
    def send_keys(self, text: str, clear: bool = False):
        """
        发送文本（需要先聚焦到输入框）
        
        Args:
            text: 要输入的文本
            clear: 是否先清空
        """
        self._ensure_connected()
        self._device.send_keys(text, clear=clear)
    
    def set_input_ime(self, enable: bool = True):
        """
        设置是否使用 FastInputIME 输入法
        
        Args:
            enable: 是否启用
        """
        self._ensure_connected()
        self._device.set_fastinput_ime(enable)
    
    def press(self, key: Union[str, int]):
        """
        按键操作
        
        Args:
            key: 按键名称或keycode，支持:
                 'home', 'back', 'menu', 'search', 'enter', 'delete',
                 'recent', 'volume_up', 'volume_down', 'volume_mute',
                 'camera', 'power' 等
        """
        self._ensure_connected()
        self._device.press(key)
    
    def home(self):
        """返回主屏幕"""
        self._ensure_connected()
        self._device.press("home")
    
    def back(self):
        """返回上一页"""
        self._ensure_connected()
        self._device.press("back")
    
    def recent(self):
        """打开最近任务"""
        self._ensure_connected()
        self._device.press("recent")
    
    def screen_on(self):
        """点亮屏幕"""
        self._ensure_connected()
        self._device.screen_on()
    
    def screen_off(self):
        """关闭屏幕"""
        self._ensure_connected()
        self._device.screen_off()
    
    def is_screen_on(self) -> bool:
        """检查屏幕是否点亮"""
        self._ensure_connected()
        return self._device.info.get('screenOn', False)
    
    def unlock(self):
        """解锁屏幕"""
        self._ensure_connected()
        self._device.unlock()
    
    def open_notification(self):
        """打开通知栏"""
        self._ensure_connected()
        self._device.open_notification()
    
    def open_quick_settings(self):
        """打开快速设置"""
        self._ensure_connected()
        self._device.open_quick_settings()
    
    def get_clipboard(self) -> str:
        """获取剪贴板内容"""
        self._ensure_connected()
        return self._device.clipboard or ''
    
    def set_clipboard(self, text: str):
        """设置剪贴板内容"""
        self._ensure_connected()
        self._device.set_clipboard(text)
    
    def dump_hierarchy(self, use_adb: bool = True) -> str:
        """
        获取UI层级结构（XML格式）
        
        Args:
            use_adb: 是否使用adb命令获取（更完整，推荐）
            
        Returns:
            UI层级的XML字符串
        """
        self._ensure_connected()
        
        if use_adb:
            try:
                # 使用 adb shell uiautomator dump 获取更完整的 UI 层级
                dump_path = '/sdcard/ui_dump.xml'
                
                # 先删除旧文件
                self._device.shell(f'rm -f {dump_path}')
                
                # dump UI hierarchy 到文件
                result = self._device.shell(f'uiautomator dump {dump_path}')
                
                # 读取文件内容
                xml_content = self._device.shell(f'cat {dump_path}').output
                
                # 清理临时文件
                self._device.shell(f'rm -f {dump_path}')
                
                if xml_content and '<?xml' in xml_content:
                    return xml_content.strip()
                else:
                    # 如果 adb 方式失败，回退到 uiautomator2 内置方法
                    return self._device.dump_hierarchy()
                    
            except Exception as e:
                print(f"adb dump_hierarchy 失败: {e}，使用内置方法")
                return self._device.dump_hierarchy()
        else:
            return self._device.dump_hierarchy()
    
    def get_ui_elements(self) -> list:
        """
        获取所有UI元素信息
        
        Returns:
            UI元素列表
        """
        self._ensure_connected()
        
        hierarchy_xml = self.dump_hierarchy(use_adb=True)
        root = ET.fromstring(hierarchy_xml)
        
        elements = []
        
        def parse_node(node, depth=0):
            attribs = node.attrib
            element = {
                'class': attribs.get('class', ''),
                'text': attribs.get('text', ''),
                'resource_id': attribs.get('resource-id', ''),
                'content_desc': attribs.get('content-desc', ''),
                'clickable': attribs.get('clickable', 'false') == 'true',
                'bounds': attribs.get('bounds', ''),
                'depth': depth
            }
            
            # 只添加有意义的元素
            if element['text'] or element['content_desc'] or element['clickable']:
                elements.append(element)
            
            for child in node:
                parse_node(child, depth + 1)
        
        parse_node(root)
        return elements
    
    def find(self, **kwargs):
        """
        通用元素查找
        
        Args:
            **kwargs: 选择器参数，支持:
                text, textContains, textMatches, textStartsWith
                className, classNameMatches
                description, descriptionContains, descriptionMatches, descriptionStartsWith
                resourceId, resourceIdMatches
                checkable, checked, clickable, longClickable
                scrollable, enabled, focusable, focused, selected
                packageName, packageNameMatches
                index, instance
                
        Returns:
            UiObject 对象
        """
        self._ensure_connected()
        return self._device(**kwargs)
    
    def xpath(self, xpath_expr: str):
        """
        通过XPath查找元素
        
        Args:
            xpath_expr: XPath表达式
            
        Returns:
            XPathSelector 对象
        """
        self._ensure_connected()
        return self._device.xpath(xpath_expr)
    
    def wait_element(self, timeout: float = 10, **kwargs) -> bool:
        """
        等待元素出现
        
        Args:
            timeout: 超时时间（秒）
            **kwargs: 选择器参数
            
        Returns:
            是否找到元素
        """
        self._ensure_connected()
        return self._device(**kwargs).wait(timeout=timeout)
    
    def wait_gone(self, timeout: float = 10, **kwargs) -> bool:
        """
        等待元素消失
        
        Args:
            timeout: 超时时间（秒）
            **kwargs: 选择器参数
            
        Returns:
            元素是否已消失
        """
        self._ensure_connected()
        return self._device(**kwargs).wait_gone(timeout=timeout)
    
    def click_element(self, **kwargs) -> bool:
        """
        通过选择器点击元素
        
        Args:
            **kwargs: 选择器参数
            
        Returns:
            是否成功点击
        """
        self._ensure_connected()
        element = self._device(**kwargs)
        if element.exists:
            element.click()
            return True
        return False
    
    def get_current_app(self) -> Dict[str, str]:
        """获取当前前台应用信息"""
        self._ensure_connected()
        current = self._device.app_current()
        return {
            'package': current.get('package', ''),
            'activity': current.get('activity', '')
        }
    
    def app_start(self, package: str, activity: Optional[str] = None, wait: bool = True):
        """
        启动应用
        
        Args:
            package: 应用包名
            activity: Activity名（可选）
            wait: 是否等待应用启动
        """
        self._ensure_connected()
        self._device.app_start(package, activity=activity, wait=wait)
    
    def app_stop(self, package: str):
        """停止应用"""
        self._ensure_connected()
        self._device.app_stop(package)
    
    def app_clear(self, package: str):
        """清除应用数据"""
        self._ensure_connected()
        self._device.app_clear(package)
    
    def app_install(self, apk_path: str):
        """安装应用"""
        self._ensure_connected()
        self._device.app_install(apk_path)
    
    def app_uninstall(self, package: str):
        """卸载应用"""
        self._ensure_connected()
        self._device.app_uninstall(package)
    
    def app_list(self, filter: str = None) -> list:
        """
        获取已安装应用列表
        
        Args:
            filter: 过滤条件 'third' 或 'system'
        """
        self._ensure_connected()
        return self._device.app_list(filter=filter)
    
    def app_info(self, package: str) -> Dict:
        """获取应用信息"""
        self._ensure_connected()
        return self._device.app_info(package)
    
    def app_wait(self, package: str, timeout: float = 20, front: bool = False) -> bool:
        """
        等待应用运行
        
        Args:
            package: 应用包名
            timeout: 超时时间
            front: 是否等待应用到前台
        """
        self._ensure_connected()
        pid = self._device.app_wait(package, timeout=timeout, front=front)
        return pid is not None
    
    def shell(self, cmd: str) -> str:
        """
        执行shell命令
        
        Args:
            cmd: 命令字符串
            
        Returns:
            命令输出
        """
        self._ensure_connected()
        result = self._device.shell(cmd)
        return result.output if hasattr(result, 'output') else str(result)
    
    def push(self, src: str, dst: str):
        """推送文件到设备"""
        self._ensure_connected()
        self._device.push(src, dst)
    
    def pull(self, src: str, dst: str):
        """从设备拉取文件"""
        self._ensure_connected()
        self._device.pull(src, dst)
    
    def window_size(self) -> tuple:
        """获取屏幕尺寸"""
        self._ensure_connected()
        return self._device.window_size()
    
    def open_url(self, url: str):
        """在浏览器中打开URL"""
        self._ensure_connected()
        self._device.open_url(url)
    
    def toast_show(self, text: str, duration: float = 1.0):
        """显示Toast消息"""
        self._ensure_connected()
        self._device.toast.show(text, duration)
    
    def toast_get_message(self, wait_timeout: float = 10, cache_timeout: float = 10, default: str = None) -> str:
        """获取Toast消息"""
        self._ensure_connected()
        return self._device.toast.get_message(wait_timeout, cache_timeout, default)

if __name__ == '__main__':
    dut = DeviceService()
    dut.connect("10.1.22.60:36941")
    print(dut.dump_hierarchy())