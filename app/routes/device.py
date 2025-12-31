from flask import Blueprint, jsonify, request
from app.services.device_service import DeviceService
from app.services.wireless_service import WirelessService

device_bp = Blueprint('device', __name__)

# 设备服务实例
device_service = DeviceService()
wireless_service = WirelessService()


@device_bp.route('/list', methods=['GET'])
def list_devices():
    """获取已连接的ADB设备列表"""
    try:
        devices = DeviceService.list_devices()
        return jsonify({'success': True, 'data': devices})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/connect', methods=['POST'])
def connect_device():
    """连接设备"""
    data = request.get_json() or {}
    device_serial = data.get('serial')
    
    try:
        result = device_service.connect(device_serial)
        return jsonify({'success': True, 'message': '设备连接成功', 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': f'连接失败: {str(e)}'}), 500


@device_bp.route('/disconnect', methods=['POST'])
def disconnect_device():
    """断开设备连接"""
    try:
        device_service.disconnect()
        return jsonify({'success': True, 'message': '设备已断开'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/screenshot', methods=['GET'])
def get_screenshot():
    """获取设备截图"""
    try:
        screenshot_base64 = device_service.get_screenshot()
        return jsonify({'success': True, 'data': screenshot_base64})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/info', methods=['GET'])
def get_device_info():
    """获取设备信息"""
    try:
        info = device_service.get_device_info()
        return jsonify({'success': True, 'data': info})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/click', methods=['POST'])
def click():
    """点击操作"""
    data = request.get_json()
    x = data.get('x')
    y = data.get('y')
    
    try:
        device_service.click(x, y)
        return jsonify({'success': True, 'message': f'点击 ({x}, {y}) 成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/swipe', methods=['POST'])
def swipe():
    """滑动操作"""
    data = request.get_json()
    start_x = data.get('start_x')
    start_y = data.get('start_y')
    end_x = data.get('end_x')
    end_y = data.get('end_y')
    duration = data.get('duration', 0.5)
    
    try:
        device_service.swipe(start_x, start_y, end_x, end_y, duration)
        return jsonify({'success': True, 'message': '滑动成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/input', methods=['POST'])
def input_text():
    """输入文本"""
    data = request.get_json()
    text = data.get('text', '')
    clear = data.get('clear', False)
    
    try:
        device_service.send_keys(text, clear=clear)
        return jsonify({'success': True, 'message': '输入成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/keyevent', methods=['POST'])
def key_event():
    """按键事件"""
    data = request.get_json()
    key = data.get('key')
    
    try:
        device_service.press(key)
        return jsonify({'success': True, 'message': f'按键 {key} 成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/hierarchy', methods=['GET'])
def get_hierarchy():
    """获取UI层级结构"""
    try:
        hierarchy = device_service.dump_hierarchy()
        return jsonify({'success': True, 'data': hierarchy})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ================= 无线调试 API =================

@device_bp.route('/wireless/start', methods=['POST'])
def start_wireless_pairing():
    """开始无线调试配对"""
    data = request.get_json() or {}
    timeout = data.get('timeout', 120)
    
    try:
        result = wireless_service.start_pairing(timeout=timeout)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/wireless/status', methods=['GET'])
def get_wireless_status():
    """获取无线调试配对状态"""
    try:
        result = wireless_service.get_status()
        return jsonify({'success': True, **result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@device_bp.route('/wireless/stop', methods=['POST'])
def stop_wireless_pairing():
    """停止无线调试配对"""
    try:
        wireless_service.stop_pairing()
        return jsonify({'success': True, 'message': '已停止配对'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

