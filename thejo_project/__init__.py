"""더 줘 — 판매점 사장님이 인센티브 환수 위험과 놓치고 있는 수익 기회를 놓치지 않게 돕는 에이전트.

Command Center(command_center/app.py)에 Blueprint 로 등록되어 /thejo/ 아래에서 함께 돈다.
별도 서버·별도 포트로 띄우지 않는다.
"""
from thejo_project.routes import thejo_bp

__all__ = ["thejo_bp"]
