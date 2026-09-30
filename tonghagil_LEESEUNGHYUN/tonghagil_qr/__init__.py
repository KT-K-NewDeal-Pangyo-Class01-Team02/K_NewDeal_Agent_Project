"""통하길 QR — 행사 현장 안내·KT 부스 위치·스탬프 이벤트 에이전트 (이승현).

Command Center(command_center/app.py)에 Blueprint 로 등록되어 /qr/ 아래에서 함께 돈다.
별도 서버·별도 포트로 띄우지 않는다.
"""
from .routes import qr_bp

__all__ = ["qr_bp"]
