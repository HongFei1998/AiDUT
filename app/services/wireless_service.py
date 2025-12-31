"""
无线调试服务 - Android 11+ 无线 ADB 配对和连接
通过二维码配对和 mDNS 服务发现实现
"""

import subprocess
import threading
import time
import base64
from io import BytesIO
from random import randint
from shutil import which
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from zeroconf import IPVersion, ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf


# ================= 常量 =================
PAIR_TYPE = "_adb-tls-pairing._tcp.local."
CONNECT_TYPES = [
    "_adb._tcp.local.",
    "_adb-tls-connect._tcp.local.",
    "_adb-tls-pairing._tcp.local.",
]
SUCCESS_PAIR = "Successfully paired"
SUCCESS_CONNECT = "connected to"


class WirelessStatus(Enum):
    """无线调试状态"""
    IDLE = "idle"
    WAITING_SCAN = "waiting_scan"
    PAIRING = "pairing"
    PAIR_SUCCESS = "pair_success"
    PAIR_FAILED = "pair_failed"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CONNECT_FAILED = "connect_failed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class WirelessSession:
    """无线调试会话"""
    name: str
    password: int
    qr_base64: str
    status: WirelessStatus = WirelessStatus.IDLE
    message: str = ""
    device_ip: Optional[str] = None
    device_port: Optional[int] = None


class ADBWirelessListener(ServiceListener):
    """ADB 无线调试服务监听器"""
    
    def __init__(self, zeroconf: Zeroconf, session: WirelessSession, 
                 on_status_change: Optional[Callable] = None):
        self.zeroconf = zeroconf
        self.session = session
        self.on_status_change = on_status_change
        self.paired_ip: Optional[str] = None
        self.connect_browsers = []
        self._stopped = False
    
    def _update_status(self, status: WirelessStatus, message: str = ""):
        """更新状态"""
        self.session.status = status
        self.session.message = message
        if self.on_status_change:
            self.on_status_change(self.session)
    
    def stop(self):
        """停止监听"""
        self._stopped = True
    
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        if self._stopped:
            return
            
        info: ServiceInfo | None = zc.get_service_info(type_, name)
        if not info:
            return

        ip_addresses = info.ip_addresses_by_version(IPVersion.All)
        if not ip_addresses:
            return
        ip_address = ip_addresses[0].exploded

        # ========== 配对阶段 ==========
        if type_ == PAIR_TYPE and name == f"{self.session.name}.{PAIR_TYPE}":
            if self.paired_ip:
                return

            self._update_status(WirelessStatus.PAIRING, f"正在配对 {ip_address}:{info.port}")
            
            if self._pair(info, ip_address):
                self.paired_ip = ip_address
                self.session.device_ip = ip_address
                self._update_status(WirelessStatus.PAIR_SUCCESS, f"配对成功，等待连接服务...")
                
                # 监听连接服务
                for connect_type in CONNECT_TYPES:
                    try:
                        browser = ServiceBrowser(self.zeroconf, connect_type, self)
                        self.connect_browsers.append(browser)
                    except Exception:
                        pass
            return

        # ========== 连接阶段 ==========
        if self.paired_ip and ip_address == self.paired_ip and type_ in CONNECT_TYPES:
            self._update_status(WirelessStatus.CONNECTING, f"正在连接 {ip_address}:{info.port}")
            self._connect(ip_address, info.port)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def _pair(self, info: ServiceInfo, ip_address: str) -> bool:
        """执行配对"""
        cmd = f"adb pair {ip_address}:{info.port} {self.session.password}"
        try:
            process = subprocess.run(
                cmd.split(" "), 
                capture_output=True, 
                timeout=30
            )
            stdout = process.stdout.decode(errors="ignore")
            stderr = process.stderr.decode(errors="ignore")

            if process.returncode != 0:
                self._update_status(WirelessStatus.PAIR_FAILED, f"配对失败: {stderr or stdout}")
                return False

            if SUCCESS_PAIR in stdout:
                return True
            else:
                self._update_status(WirelessStatus.PAIR_FAILED, f"配对失败: {stdout}")
                return False
        except subprocess.TimeoutExpired:
            self._update_status(WirelessStatus.PAIR_FAILED, "配对超时")
            return False
        except Exception as e:
            self._update_status(WirelessStatus.PAIR_FAILED, f"配对异常: {str(e)}")
            return False

    def _connect(self, ip: str, port: int):
        """执行连接"""
        cmd = f"adb connect {ip}:{port}"
        try:
            process = subprocess.run(
                cmd.split(" "), 
                capture_output=True, 
                timeout=30
            )
            stdout = process.stdout.decode(errors="ignore")

            if SUCCESS_CONNECT in stdout:
                self.session.device_port = port
                self._update_status(WirelessStatus.CONNECTED, f"成功连接到 {ip}:{port}")
                self._stopped = True
            else:
                self._update_status(WirelessStatus.CONNECT_FAILED, f"连接失败: {stdout}")
        except subprocess.TimeoutExpired:
            self._update_status(WirelessStatus.CONNECT_FAILED, "连接超时")
        except Exception as e:
            self._update_status(WirelessStatus.CONNECT_FAILED, f"连接异常: {str(e)}")


class WirelessService:
    """无线调试服务"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._session: Optional[WirelessSession] = None
        self._zeroconf: Optional[Zeroconf] = None
        self._listener: Optional[ADBWirelessListener] = None
        self._thread: Optional[threading.Thread] = None
        self._status_callback: Optional[Callable] = None
    
    @staticmethod
    def check_adb() -> bool:
        """检查 adb 是否可用"""
        return which("adb") is not None
    
    def _generate_qr_base64(self, name: str, password: int) -> str:
        """生成二维码的 Base64 编码"""
        try:
            from qrcode import QRCode
            from qrcode.constants import ERROR_CORRECT_M
            
            qr_data = f"WIFI:T:ADB;S:{name};P:{password};;"
            
            qr = QRCode(
                version=1,
                error_correction=ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return f"data:image/png;base64,{img_base64}"
        except ImportError:
            raise Exception("需要安装 qrcode 库: pip install qrcode[pil]")
    
    def start_pairing(self, timeout: int = 120) -> Dict[str, Any]:
        """
        开始配对流程
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            包含二维码和会话信息的字典
        """
        # 检查 adb
        if not self.check_adb():
            return {
                'success': False,
                'message': 'ADB 未找到，请确保已安装并添加到 PATH'
            }
        
        # 停止之前的会话
        self.stop_pairing()
        
        # 生成配对信息
        name = "debug"
        password = randint(100000, 999999)
        
        try:
            qr_base64 = self._generate_qr_base64(name, password)
        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }
        
        # 创建会话
        self._session = WirelessSession(
            name=name,
            password=password,
            qr_base64=qr_base64,
            status=WirelessStatus.WAITING_SCAN,
            message="请扫描二维码进行配对"
        )
        
        # 启动 mDNS 监听
        try:
            self._zeroconf = Zeroconf()
            self._listener = ADBWirelessListener(
                self._zeroconf, 
                self._session,
                self._status_callback
            )
            
            # 开始监听配对服务
            ServiceBrowser(self._zeroconf, PAIR_TYPE, self._listener)
            
            # 启动超时线程
            def timeout_handler():
                time.sleep(timeout)
                if self._session and self._session.status in [
                    WirelessStatus.WAITING_SCAN, 
                    WirelessStatus.PAIRING
                ]:
                    self._session.status = WirelessStatus.TIMEOUT
                    self._session.message = "配对超时"
                    if self._status_callback:
                        self._status_callback(self._session)
                    self.stop_pairing()
            
            self._thread = threading.Thread(target=timeout_handler, daemon=True)
            self._thread.start()
            
            return {
                'success': True,
                'qr_code': qr_base64,
                'password': password,
                'status': self._session.status.value,
                'message': self._session.message
            }
            
        except Exception as e:
            self.stop_pairing()
            return {
                'success': False,
                'message': f'启动配对服务失败: {str(e)}'
            }
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前配对状态"""
        if not self._session:
            return {
                'status': WirelessStatus.IDLE.value,
                'message': '无活动会话'
            }
        
        return {
            'status': self._session.status.value,
            'message': self._session.message,
            'device_ip': self._session.device_ip,
            'device_port': self._session.device_port,
            'qr_code': self._session.qr_base64 if self._session.status == WirelessStatus.WAITING_SCAN else None
        }
    
    def stop_pairing(self):
        """停止配对流程"""
        if self._listener:
            self._listener.stop()
            self._listener = None
        
        if self._zeroconf:
            try:
                self._zeroconf.close()
            except Exception:
                pass
            self._zeroconf = None
        
        self._session = None
    
    def set_status_callback(self, callback: Callable):
        """设置状态变化回调"""
        self._status_callback = callback
    
    def is_active(self) -> bool:
        """检查是否有活动会话"""
        return self._session is not None and self._session.status in [
            WirelessStatus.WAITING_SCAN,
            WirelessStatus.PAIRING,
            WirelessStatus.PAIR_SUCCESS,
            WirelessStatus.CONNECTING
        ]

