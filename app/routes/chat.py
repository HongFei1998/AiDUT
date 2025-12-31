from flask import Blueprint, jsonify, request, Response, stream_with_context
from app.services.agent_service import AgentService
from app.services.llm_service import LLMService
import json

chat_bp = Blueprint('chat', __name__)

# 服务实例
agent_service = AgentService()
llm_service = LLMService()


@chat_bp.route('/stop', methods=['POST'])
def stop_execution():
    """停止当前任务执行"""
    agent_service.stop()
    return jsonify({'success': True, 'message': '已发送停止信号'})


@chat_bp.route('/execute', methods=['POST'])
def execute_task():
    """
    执行任务 - Agent模式（SSE流式返回）
    
    自动循环执行，每一步都返回状态
    """
    data = request.get_json()
    task = data.get('task', '')
    
    if not task:
        return jsonify({'success': False, 'message': '任务不能为空'}), 400
    
    def generate():
        try:
            for step_result in agent_service.execute_task(task):
                yield f"data: {json.dumps(step_result, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@chat_bp.route('/single-action', methods=['POST'])
def execute_single_action():
    """执行单个操作（手动模式）"""
    data = request.get_json()
    action = data.get('action', {})
    
    if not action:
        return jsonify({'success': False, 'message': '操作不能为空'}), 400
    
    result = agent_service.execute_single_action(action)
    return jsonify(result)


@chat_bp.route('/history', methods=['GET'])
def get_history():
    """获取对话历史"""
    history = llm_service.get_history()
    return jsonify({'success': True, 'data': history})


@chat_bp.route('/clear', methods=['POST'])
def clear_history():
    """清空对话历史"""
    llm_service.clear_history()
    return jsonify({'success': True, 'message': '对话历史已清空'})
