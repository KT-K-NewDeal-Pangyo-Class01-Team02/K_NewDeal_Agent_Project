"""통하길 스튜디오 — 행사 홍보 포스터 생성 에이전트 (이승현).

Command Center(command_center/app.py)에 Blueprint 로 등록되어 /studio/ 아래에서 함께 돈다.
별도 서버·별도 포트로 띄우지 않는다.
"""
from .routes import studio_bp

__all__ = ["studio_bp"]
