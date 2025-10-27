from http.server import BaseHTTPRequestHandler
import json
import base64
from io import BytesIO
from PIL import Image

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # CORS 헤더
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

            # 요청 데이터 읽기
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # base64 이미지 디코딩
            frames = []
            for frame_data in data['frames']:
                # data:image/png;base64, 또는 data:image/jpeg;base64, 제거
                img_data = frame_data.split(',')[1] if ',' in frame_data else frame_data
                img_bytes = base64.b64decode(img_data)
                img = Image.open(BytesIO(img_bytes))
                # RGBA를 RGB로 변환 (WebP 호환성)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                frames.append(img)

            # WebP 애니메이션 생성
            output = BytesIO()
            frames[0].save(
                output,
                format='WEBP',
                save_all=True,
                append_images=frames[1:],
                duration=800,  # 0.8초
                loop=0,  # 무한 반복
                quality=85,
                method=6
            )

            # base64로 인코딩
            output.seek(0)
            webp_base64 = base64.b64encode(output.read()).decode('utf-8')

            # 응답
            response = {
                'success': True,
                'webp': f'data:image/webp;base64,{webp_base64}',
                'size': len(output.getvalue())
            }
            
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = {
                'success': False,
                'error': str(e)
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
