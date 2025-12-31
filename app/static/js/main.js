/**
 * AI手机助手 - 前端主逻辑
 */

class AIPhoneAssistant {
    constructor() {
        this.isConnected = false;
        this.isExecuting = false;
        this.screenRefreshInterval = null;
        this.wirelessPollingInterval = null;
        this.currentTab = 'usb';
        
        this.initElements();
        this.bindEvents();
    }

    initElements() {
        this.deviceStatus = document.getElementById('deviceStatus');
        this.deviceInfo = document.getElementById('deviceInfo');
        this.deviceScreen = document.getElementById('deviceScreen');
        this.screenPlaceholder = document.getElementById('screenPlaceholder');
        this.touchCanvas = document.getElementById('touchCanvas');
        this.screenWrapper = document.getElementById('screenWrapper');
        
        this.btnConnect = document.getElementById('btnConnect');
        this.btnRefresh = document.getElementById('btnRefresh');
        this.btnClear = document.getElementById('btnClear');
        this.btnSend = document.getElementById('btnSend');
        this.btnStop = document.getElementById('btnStop');
        
        this.chatContainer = document.getElementById('chatContainer');
        this.messageInput = document.getElementById('messageInput');
        
        this.connectModal = document.getElementById('connectModal');
        this.deviceSerial = document.getElementById('deviceSerial');
        this.btnConfirmConnect = document.getElementById('btnConfirmConnect');
        this.btnCancel = document.getElementById('btnCancel');
        this.modalClose = document.getElementById('modalClose');
        this.btnRefreshDevices = document.getElementById('btnRefreshDevices');
        this.deviceListHint = document.getElementById('deviceListHint');
        
        // 无线调试相关元素
        this.usbPanel = document.getElementById('usbPanel');
        this.wirelessPanel = document.getElementById('wirelessPanel');
        this.usbFooter = document.getElementById('usbFooter');
        this.wirelessIdle = document.getElementById('wirelessIdle');
        this.wirelessPairing = document.getElementById('wirelessPairing');
        this.wirelessSuccess = document.getElementById('wirelessSuccess');
        this.wirelessQRCode = document.getElementById('wirelessQRCode');
        this.wirelessStatus = document.getElementById('wirelessStatus');
        this.wirelessDevice = document.getElementById('wirelessDevice');
        this.btnStartPair = document.getElementById('btnStartPair');
        this.btnStopPair = document.getElementById('btnStopPair');
        
        this.loadingOverlay = document.getElementById('loadingOverlay');
    }

    bindEvents() {
        this.btnConnect.addEventListener('click', () => this.showConnectModal());
        this.btnConfirmConnect.addEventListener('click', () => this.connectDevice());
        this.btnCancel.addEventListener('click', () => this.hideConnectModal());
        this.modalClose.addEventListener('click', () => this.hideConnectModal());
        this.btnRefreshDevices.addEventListener('click', () => this.fetchDeviceList());
        
        // 标签切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
        
        // 无线调试事件
        this.btnStartPair.addEventListener('click', () => this.startWirelessPairing());
        this.btnStopPair.addEventListener('click', () => this.stopWirelessPairing());
        
        this.btnRefresh.addEventListener('click', () => this.refreshScreen());
        this.btnClear.addEventListener('click', () => this.clearChat());
        
        this.btnSend.addEventListener('click', () => this.executeTask());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.executeTask();
            }
        });
        
        this.btnStop.addEventListener('click', () => this.stopExecution());
        
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
        });
        
        document.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.messageInput.value = btn.dataset.msg;
                this.executeTask();
            });
        });
        
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.addEventListener('click', () => this.pressKey(btn.dataset.key));
        });
        
        this.touchCanvas.addEventListener('click', (e) => this.handleScreenClick(e));
        
        this.connectModal.querySelector('.modal-overlay').addEventListener('click', () => {
            this.hideConnectModal();
        });
    }

    showLoading(text = '正在处理...') {
        this.loadingOverlay.querySelector('.loading-text').textContent = text;
        this.loadingOverlay.classList.remove('hidden');
    }

    hideLoading() {
        this.loadingOverlay.classList.add('hidden');
    }

    showConnectModal() {
        this.connectModal.classList.remove('hidden');
        // 重置到 USB 标签
        this.switchTab('usb');
        this.fetchDeviceList();
        // 重置无线调试状态
        this.resetWirelessUI();
    }

    hideConnectModal() {
        this.connectModal.classList.add('hidden');
        // 停止无线配对轮询
        this.stopWirelessPolling();
    }

    switchTab(tab) {
        this.currentTab = tab;
        
        // 更新标签按钮状态
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        // 切换面板
        this.usbPanel.classList.toggle('active', tab === 'usb');
        this.wirelessPanel.classList.toggle('active', tab === 'wireless');
        
        // 切换底部按钮
        this.usbFooter.style.display = tab === 'usb' ? 'flex' : 'none';
        
        // 如果切换到无线标签，停止USB轮询；反之亦然
        if (tab === 'wireless') {
            this.stopWirelessPolling();
            this.resetWirelessUI();
        }
    }

    resetWirelessUI() {
        this.wirelessIdle.classList.remove('hidden');
        this.wirelessPairing.classList.add('hidden');
        this.wirelessSuccess.classList.add('hidden');
        this.wirelessStatus.className = 'wireless-status';
    }

    async fetchDeviceList() {
        // 显示加载状态
        this.deviceSerial.innerHTML = '<option value="">正在获取设备列表...</option>';
        this.deviceSerial.disabled = true;
        this.btnRefreshDevices.disabled = true;
        this.deviceListHint.textContent = '正在扫描已连接的设备...';
        
        try {
            const response = await fetch('/api/device/list');
            const data = await response.json();
            
            if (data.success) {
                const devices = data.data;
                this.deviceSerial.innerHTML = '';
                
                if (devices.length === 0) {
                    this.deviceSerial.innerHTML = '<option value="">未发现设备</option>';
                    this.deviceListHint.textContent = '未发现已连接的设备，请检查 USB 连接和 USB 调试是否已开启';
                    this.deviceListHint.style.color = 'var(--error)';
                } else {
                    // 添加一个提示选项
                    if (devices.length > 1) {
                        this.deviceSerial.innerHTML = '<option value="">请选择设备...</option>';
                    }
                    
                    // 添加设备选项
                    devices.forEach(device => {
                        const option = document.createElement('option');
                        option.value = device.serial;
                        option.textContent = device.serial;
                        this.deviceSerial.appendChild(option);
                    });
                    
                    // 如果只有一个设备，自动选中
                    if (devices.length === 1) {
                        this.deviceSerial.value = devices[0].serial;
                    }
                    
                    this.deviceListHint.textContent = `发现 ${devices.length} 个设备`;
                    this.deviceListHint.style.color = 'var(--success)';
                }
            } else {
                this.deviceSerial.innerHTML = '<option value="">获取设备列表失败</option>';
                this.deviceListHint.textContent = data.message || '获取设备列表失败';
                this.deviceListHint.style.color = 'var(--error)';
            }
        } catch (error) {
            this.deviceSerial.innerHTML = '<option value="">获取设备列表失败</option>';
            this.deviceListHint.textContent = '无法连接到服务器';
            this.deviceListHint.style.color = 'var(--error)';
        } finally {
            this.deviceSerial.disabled = false;
            this.btnRefreshDevices.disabled = false;
        }
    }

    // ================= 无线调试方法 =================
    
    async startWirelessPairing() {
        this.wirelessIdle.classList.add('hidden');
        this.wirelessPairing.classList.remove('hidden');
        this.wirelessSuccess.classList.add('hidden');
        
        this.updateWirelessStatus('等待服务启动...', 'pairing');
        
        try {
            const response = await fetch('/api/device/wireless/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ timeout: 120 })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.wirelessQRCode.src = data.qr_code;
                this.updateWirelessStatus('请使用手机扫描二维码', 'pairing');
                
                // 开始轮询状态
                this.startWirelessPolling();
            } else {
                this.updateWirelessStatus(data.message || '启动失败', 'error');
            }
        } catch (error) {
            this.updateWirelessStatus('启动配对服务失败: ' + error.message, 'error');
        }
    }

    async stopWirelessPairing() {
        this.stopWirelessPolling();
        
        try {
            await fetch('/api/device/wireless/stop', { method: 'POST' });
        } catch (error) {
            console.error('停止配对失败:', error);
        }
        
        this.resetWirelessUI();
    }

    startWirelessPolling() {
        this.stopWirelessPolling();
        
        this.wirelessPollingInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/device/wireless/status');
                const data = await response.json();
                
                if (data.success) {
                    this.handleWirelessStatus(data);
                }
            } catch (error) {
                console.error('获取状态失败:', error);
            }
        }, 1000);
    }

    stopWirelessPolling() {
        if (this.wirelessPollingInterval) {
            clearInterval(this.wirelessPollingInterval);
            this.wirelessPollingInterval = null;
        }
    }

    handleWirelessStatus(data) {
        const status = data.status;
        const message = data.message || '';
        
        switch (status) {
            case 'waiting_scan':
                this.updateWirelessStatus('请使用手机扫描二维码', 'pairing');
                break;
            case 'pairing':
                this.updateWirelessStatus('正在配对...', 'pairing');
                break;
            case 'pair_success':
                this.updateWirelessStatus('配对成功，等待连接...', 'pairing');
                break;
            case 'connecting':
                this.updateWirelessStatus('正在连接设备...', 'pairing');
                break;
            case 'connected':
                this.stopWirelessPolling();
                this.showWirelessSuccess(data.device_ip, data.device_port);
                // 自动连接到设备
                this.connectWirelessDevice(data.device_ip, data.device_port);
                break;
            case 'pair_failed':
            case 'connect_failed':
            case 'error':
                this.updateWirelessStatus(message || '操作失败', 'error');
                break;
            case 'timeout':
                this.updateWirelessStatus('配对超时，请重试', 'error');
                this.stopWirelessPolling();
                break;
            case 'idle':
                // 无活动会话
                break;
        }
    }

    updateWirelessStatus(message, type = '') {
        const statusIcon = this.wirelessStatus.querySelector('.status-icon');
        const statusMessage = this.wirelessStatus.querySelector('.status-message');
        
        statusMessage.textContent = message;
        this.wirelessStatus.className = 'wireless-status ' + type;
        
        if (type === 'pairing') {
            statusIcon.textContent = '⏳';
        } else if (type === 'success') {
            statusIcon.textContent = '✅';
        } else if (type === 'error') {
            statusIcon.textContent = '❌';
        }
    }

    showWirelessSuccess(ip, port) {
        this.wirelessPairing.classList.add('hidden');
        this.wirelessSuccess.classList.remove('hidden');
        this.wirelessDevice.textContent = `设备地址: ${ip}:${port}`;
    }

    async connectWirelessDevice(ip, port) {
        const serial = `${ip}:${port}`;
        
        this.hideConnectModal();
        this.showLoading('正在连接无线设备...');
        
        try {
            const response = await fetch('/api/device/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial: serial })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.isConnected = true;
                this.updateConnectionStatus(true, data.data);
                this.showScreen();
                this.startScreenRefresh();
                this.showToast('无线设备连接成功！', 'success');
            } else {
                this.showToast(data.message || '连接失败', 'error');
            }
        } catch (error) {
            this.showToast('连接失败: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    setExecutingState(executing) {
        this.isExecuting = executing;
        if (executing) {
            this.btnSend.classList.add('hidden');
            this.btnStop.classList.remove('hidden');
            this.messageInput.disabled = true;
        } else {
            this.btnSend.classList.remove('hidden');
            this.btnStop.classList.add('hidden');
            this.messageInput.disabled = false;
        }
    }

    async stopExecution() {
        try {
            await fetch('/api/chat/stop', { method: 'POST' });
            this.showToast('正在停止...', 'warning');
        } catch (error) {
            console.error('停止失败:', error);
        }
    }

    async connectDevice() {
        const serial = this.deviceSerial.value.trim();
        
        // 验证是否选择了设备
        if (!serial) {
            this.showToast('请先选择一个设备', 'warning');
            return;
        }
        
        this.hideConnectModal();
        this.showLoading('正在连接设备...');
        
        try {
            const response = await fetch('/api/device/connect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ serial: serial })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.isConnected = true;
                this.updateConnectionStatus(true, data.data);
                this.showScreen();
                this.startScreenRefresh();
                this.showToast('设备连接成功！', 'success');
            } else {
                this.showToast(data.message || '连接失败', 'error');
            }
        } catch (error) {
            this.showToast('连接失败: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    updateConnectionStatus(connected, info = null) {
        const statusDot = this.deviceStatus.querySelector('.status-dot');
        const statusText = this.deviceStatus.querySelector('.status-text');
        
        if (connected) {
            statusDot.classList.remove('disconnected');
            statusDot.classList.add('connected');
            statusText.textContent = '已连接';
            this.btnConnect.textContent = '连接设备';
            if (info) {
                this.deviceInfo.textContent = `${info.brand} ${info.model}`;
            }
        } else {
            statusDot.classList.add('disconnected');
            statusDot.classList.remove('connected');
            statusText.textContent = '未连接';
            this.btnConnect.textContent = '连接设备';
            this.deviceInfo.textContent = '';
        }
    }

    showScreen() {
        this.screenPlaceholder.classList.add('hidden');
        this.deviceScreen.classList.remove('hidden');
        this.touchCanvas.classList.remove('hidden');
    }

    async refreshScreen() {
        if (!this.isConnected) {
            this.showToast('请先连接设备', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/device/screenshot');
            const data = await response.json();
            if (data.success) {
                this.deviceScreen.src = data.data;
            }
        } catch (error) {
            console.error('刷新截图失败:', error);
        }
    }

    startScreenRefresh() {
        this.refreshScreen();
        this.screenRefreshInterval = setInterval(() => {
            if (!this.isExecuting) {
                this.refreshScreen();
            }
        }, 2000);
    }

    stopScreenRefresh() {
        if (this.screenRefreshInterval) {
            clearInterval(this.screenRefreshInterval);
            this.screenRefreshInterval = null;
        }
    }

    async handleScreenClick(e) {
        if (!this.isConnected || this.isExecuting) return;
        
        const rect = this.touchCanvas.getBoundingClientRect();
        const scaleX = this.deviceScreen.naturalWidth / rect.width;
        const scaleY = this.deviceScreen.naturalHeight / rect.height;
        
        const x = Math.round((e.clientX - rect.left) * scaleX);
        const y = Math.round((e.clientY - rect.top) * scaleY);
        
        this.showClickEffect(e.clientX - rect.left, e.clientY - rect.top);
        
        try {
            await fetch('/api/device/click', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x, y })
            });
            setTimeout(() => this.refreshScreen(), 500);
        } catch (error) {
            console.error('点击失败:', error);
        }
    }

    showClickEffect(x, y) {
        const effect = document.createElement('div');
        effect.style.cssText = `
            position: absolute;
            left: ${x}px;
            top: ${y}px;
            width: 30px;
            height: 30px;
            margin: -15px;
            border: 2px solid var(--primary);
            border-radius: 50%;
            animation: clickEffect 0.5s ease-out forwards;
            pointer-events: none;
        `;
        this.screenWrapper.appendChild(effect);
        setTimeout(() => effect.remove(), 500);
    }

    async pressKey(key) {
        if (!this.isConnected || this.isExecuting) return;
        
        try {
            await fetch('/api/device/keyevent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key })
            });
            setTimeout(() => this.refreshScreen(), 500);
        } catch (error) {
            console.error('按键失败:', error);
        }
    }

    async executeTask() {
        const task = this.messageInput.value.trim();
        if (!task) return;
        
        if (!this.isConnected) {
            this.showToast('请先连接设备', 'warning');
            return;
        }
        
        if (this.isExecuting) {
            this.showToast('正在执行中...', 'warning');
            return;
        }
        
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        
        const welcomeMsg = this.chatContainer.querySelector('.welcome-message');
        if (welcomeMsg) welcomeMsg.remove();
        
        // 添加用户消息
        this.addMessage('user', task);
        
        this.setExecutingState(true);
        
        try {
            const response = await fetch('/api/chat/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task })
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            this.handleStepResult(data);
                        } catch (e) {
                            console.error('解析失败:', e);
                        }
                    }
                }
            }
        } catch (error) {
            this.addSystemMessage('❌ 执行出错: ' + error.message, 'error');
        } finally {
            this.setExecutingState(false);
            this.refreshScreen();
        }
    }

    handleStepResult(data) {
        // 更新截图
        if (data.screenshot) {
            this.deviceScreen.src = data.screenshot;
        }
        
        switch (data.type) {
            case 'start':
            case 'info':
            case 'update':
                this.addSystemMessage(data.message, 'info');
                break;
            case 'thinking':
                this.updateOrAddThinking(data.message);
                break;
            case 'action':
                this.removeThinking();
                this.addSystemMessage(data.message, 'action', data.action, data.debug);
                break;
            case 'done':
                this.addSystemMessage(data.message, 'success');
                break;
            case 'completed':
                this.addSystemMessage(data.message, 'success', null, data.debug);
                break;
            case 'failed':
            case 'error':
                this.removeThinking();
                this.addSystemMessage(data.message, 'error', null, data.debug);
                break;
            case 'stopped':
                this.removeThinking();
                this.addSystemMessage(data.message, 'warning');
                break;
            case 'warning':
                this.addSystemMessage(data.message, 'warning');
                break;
        }
        
        this.scrollToBottom();
    }

    addMessage(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.innerHTML = `
            <div class="message-avatar">${role === 'user' ? '👤' : '🤖'}</div>
            <div class="message-content">${this.escapeHtml(content)}</div>
        `;
        this.chatContainer.appendChild(div);
        this.scrollToBottom();
    }

    addSystemMessage(message, type = 'info', action = null, debug = null) {
        const div = document.createElement('div');
        div.className = `system-message ${type}`;
        
        let content = `<span class="system-text">${this.escapeHtml(message)}</span>`;
        
        if (action) {
            content += `<code class="action-code">${JSON.stringify(action)}</code>`;
        }
        
        if (debug) {
            const debugId = 'debug-' + Date.now();
            content += `
                <button class="debug-btn" onclick="app.toggleDebug('${debugId}')">详情</button>
                <div class="debug-panel hidden" id="${debugId}">
                    <div><b>发送:</b><pre>${this.escapeHtml(debug.user_message || '')}</pre></div>
                    <div><b>响应:</b><pre>${this.escapeHtml(debug.raw_response || '')}</pre></div>
                </div>
            `;
        }
        
        div.innerHTML = content;
        this.chatContainer.appendChild(div);
    }

    updateOrAddThinking(message) {
        let thinking = this.chatContainer.querySelector('.thinking-message');
        if (thinking) {
            thinking.querySelector('.system-text').textContent = message;
        } else {
            const div = document.createElement('div');
            div.className = 'system-message thinking-message';
            div.innerHTML = `<span class="system-text">${this.escapeHtml(message)}</span><span class="thinking-dots"></span>`;
            this.chatContainer.appendChild(div);
        }
        this.scrollToBottom();
    }

    removeThinking() {
        const thinking = this.chatContainer.querySelector('.thinking-message');
        if (thinking) thinking.remove();
    }

    toggleDebug(id) {
        const panel = document.getElementById(id);
        if (panel) panel.classList.toggle('hidden');
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async clearChat() {
        try {
            await fetch('/api/chat/clear', { method: 'POST' });
        } catch (error) {
            console.error('清空失败:', error);
        }
        
        this.chatContainer.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🤖</div>
                <h3>你好！我是AI手机助手</h3>
                <p>告诉我你想做什么，我会自动帮你完成</p>
                <div class="quick-actions">
                    <button class="quick-btn" data-msg="打开微信">打开微信</button>
                    <button class="quick-btn" data-msg="打开设置">打开设置</button>
                    <button class="quick-btn" data-msg="返回桌面">返回桌面</button>
                    <button class="quick-btn" data-msg="向下滑动">向下滑动</button>
                </div>
            </div>
        `;
        
        document.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.messageInput.value = btn.dataset.msg;
                this.executeTask();
            });
        });
    }

    scrollToBottom() {
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            background: ${type === 'success' ? 'var(--success)' : type === 'error' ? 'var(--error)' : type === 'warning' ? 'var(--warning)' : 'var(--primary)'};
            color: white;
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-md);
            z-index: 3000;
            animation: slideIn 0.3s ease;
        `;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.animation = 'fadeOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

const style = document.createElement('style');
style.textContent = `
    @keyframes clickEffect {
        0% { transform: scale(0.5); opacity: 1; }
        100% { transform: scale(2); opacity: 0; }
    }
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
`;
document.head.appendChild(style);

const app = new AIPhoneAssistant();
