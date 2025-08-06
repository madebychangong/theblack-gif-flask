from flask import Flask, request, jsonify, send_from_directory
import os
import asyncio
import time
import requests
import gc  # 🔧 Leapcell: 메모리 정리용 추가
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from PIL import Image
import io

# 환경변수 로드
load_dotenv()

app = Flask(__name__)

# =================================
# Supabase 설정 (HTTP 직접 요청)
# =================================

SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ssnmitgehgzzcpmqwhzt.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNzbm1pdGdlaGd6emNwbXF3aHp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMzNjI1MDgsImV4cCI6MjA2ODkzODUwOH0.u3FrSDh5qYeccQmn0PkOs4nfqIhXLSFHhpWj2JXhTrA')

print(f"🔗 Supabase URL: {SUPABASE_URL}")
print(f"🔐 Supabase Key: {SUPABASE_KEY[:20]}...")

# Supabase Storage API 엔드포인트
STORAGE_API_URL = f"{SUPABASE_URL}/storage/v1/object"
BUCKET_NAME = "changong-images"

def test_supabase_connection():
    """Supabase 연결 테스트"""
    try:
        # Storage API 테스트
        headers = {
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json'
        }
        
        # 버킷 목록 조회로 연결 테스트
        response = requests.get(f"{SUPABASE_URL}/storage/v1/bucket", headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ Supabase Storage 연결 성공")
            return True
        else:
            print(f"❌ Supabase 연결 실패: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Supabase 연결 테스트 실패: {e}")
        return False

# =================================
# 🚀 새로운 GIF 생성 핵심 함수들 (브라우저 1개 방식)
# =================================

def render_template_to_html(text):
    """
    사용자 텍스트를 받아서 쇼핑몰형 HTML 문자열 생성
    🔧 Flask 템플릿 엔진 대신 단순 문자열 치환 방식 사용 (안전함)
    
    Args:
        text (str): 사용자가 입력한 텍스트
    
    Returns:
        str: 완성된 HTML 문자열
    """
    try:
        # 1. 줄바꿈을 HTML <br> 태그로 변환
        formatted_text = text.replace('\n', '<br>')
        
        # 2. 쇼핑몰형 템플릿 파일 읽기
        template_path = os.path.join('templates', 'theblackempty.html')
        with open(template_path, 'r', encoding='utf-8') as file:
            template_content = file.read()
        
        # 3. 🔧 단순 문자열 치환 (Flask 템플릿 엔진 사용 안 함)
        # {{text|safe}} 를 실제 텍스트로 치환
        html_content = template_content.replace('{{text|safe}}', formatted_text)
        
        # 혹시 다른 변수들도 있다면 처리
        html_content = html_content.replace('{{text}}', formatted_text)
        
        return html_content
        
    except Exception as e:
        raise Exception(f"HTML 템플릿 생성 실패: {str(e)}")

async def capture_animation_frames(html_content, frame_count=20, frame_interval=150):
    """
    🚀 새로운 방식: 브라우저 1개로 연속 스크린샷 캡처
    CSS 애니메이션이 진행되는 동안 여러 프레임을 연속으로 캡처
    
    Args:
        html_content (str): 렌더링할 HTML 문자열 (쇼핑몰형 템플릿)
        frame_count (int): 캡처할 프레임 수 (기본값: 20개)
        frame_interval (int): 프레임 간 간격 (밀리초, 기본값: 150ms)
    
    Returns:
        list: PIL Image 객체들의 리스트
    """
    browser = None
    images = []
    
    try:
        print(f"🎬 브라우저 1개로 {frame_count}프레임 연속 캡처 시작")
        
        # 1. Playwright 브라우저 실행 (1번만!)
        async with async_playwright() as p:
            # 🔧 Leapcell: 브라우저 args 최적화
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-web-security',
                    '--no-first-run',
                    '--single-process'  # Serverless 환경용
                ]
            )
            
            # 2. 새 페이지 생성 (1번만!)
            page = await browser.new_page()
            
            # 3. 뷰포트 크기 설정
            await page.set_viewport_size({"width": 720, "height": 900})
            
            # 4. HTML 콘텐츠 로드 (1번만!)
            await page.set_content(html_content, wait_until='networkidle')
            
            # 5. 폰트 로딩 대기
            await page.wait_for_timeout(2000)  # 2초 대기
            await page.evaluate("document.fonts.ready")
            
            # 6. render-target 요소 찾기
            render_target = await page.query_selector('.render-target')
            if not render_target:
                raise Exception("render-target 요소를 찾을 수 없습니다")
            
            # 7. 🎨 연속 스크린샷 캡처 (브라우저는 그대로 둠!)
            print(f"📸 {frame_count}개 프레임 연속 캡처 중...")
            
            for i in range(frame_count):
                # 프레임 간격 대기 (CSS 애니메이션이 자연스럽게 진행됨)
                if i > 0:  # 첫 번째 프레임은 바로 캡처
                    await page.wait_for_timeout(frame_interval)
                
                # 스크린샷 촬영
                screenshot_bytes = await render_target.screenshot(type='png')
                
                # PIL Image 객체로 변환
                image = Image.open(io.BytesIO(screenshot_bytes))
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                
                images.append(image)
                print(f"✅ 프레임 {i+1}/{frame_count} 캡처 완료")
            
            # 8. 브라우저 종료 (1번만!)
            await browser.close()
        
        print(f"🎉 총 {len(images)}개 프레임 캡처 완료!")
        return images
        
    except Exception as e:
        # 브라우저 정리
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        # 이미지 객체 정리
        for img in images:
            try:
                img.close()
            except:
                pass
                
        raise Exception(f"연속 캡처 실패: {str(e)}")

def sync_capture_animation(html_content, frame_count=20, frame_interval=150):
    """
    비동기 capture_animation_frames를 동기적으로 실행하는 래퍼 함수
    """
    try:
        # 새 이벤트 루프에서 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                capture_animation_frames(html_content, frame_count, frame_interval)
            )
            return result
        finally:
            loop.close()
    except Exception as e:
        raise Exception(f"동기 캡처 실행 실패: {str(e)}")

def create_gif_from_frames_in_memory(images, duration=100):
    """
    🚀 메모리에서만 작업: PIL Image 객체들을 메모리상에서 GIF로 합성
    파일 시스템을 전혀 사용하지 않는 완전 메모리 기반 처리
    
    Args:
        images (list): PIL Image 객체들의 리스트
        duration (int): 각 프레임 지속 시간 (밀리초, 기본값: 100ms)
    
    Returns:
        bytes: GIF 바이트 데이터
    """
    try:
        print(f"🎨 메모리에서 {len(images)}개 프레임으로 GIF 생성 시작")
        
        if len(images) < 2:
            raise Exception(f"최소 2개의 프레임이 필요하지만 {len(images)}개만 있습니다")
        
        # 메모리 버퍼 생성
        gif_buffer = io.BytesIO()
        
        # 첫 번째 이미지를 기준으로 GIF 생성 (메모리에서!)
        first_image = images[0]
        other_images = images[1:]
        
        # GIF를 메모리 버퍼에 저장
        first_image.save(
            gif_buffer,
            save_all=True,
            append_images=other_images,
            duration=duration,  # 각 프레임 지속 시간 (ms)
            loop=0,  # 무한 반복
            optimize=True,  # 파일 크기 최적화
            format='GIF'
        )
        
        # 버퍼에서 바이트 데이터 추출
        gif_bytes = gif_buffer.getvalue()
        gif_buffer.close()
        
        total_duration = len(images) * duration
        print(f"✅ 메모리 GIF 생성 완료: {len(gif_bytes)} bytes")
        print(f"🎬 총 {len(images)}프레임, {total_duration}ms 재생시간")
        
        return gif_bytes
        
    except Exception as e:
        raise Exception(f"메모리 GIF 생성 실패: {str(e)}")

def upload_gif_bytes_to_supabase(gif_bytes, retries=3):
    """
    🚀 메모리의 GIF 바이트 데이터를 직접 Supabase Storage에 업로드
    파일을 디스크에 저장하지 않고 메모리에서 바로 업로드
    
    Args:
        gif_bytes (bytes): GIF 바이트 데이터
        retries (int): 실패시 재시도 횟수
    
    Returns:
        str: Public URL
    """
    try:
        print(f"📤 메모리 GIF 바이트를 Supabase에 직접 업로드: {len(gif_bytes)} bytes")
        
        # 고정 파일명 사용 (덮어쓰기)
        filename = "bg1.gif"
        
        print(f"📦 업로드 준비: {filename} ({len(gif_bytes)} bytes)")
        
        # HTTP 헤더 설정
        headers = {
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'image/gif',
            'Cache-Control': '3600'
        }
        
        # 재시도 로직으로 업로드
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                print(f"🔄 메모리 직접 업로드 시도 {attempt}/{retries}")
                
                # 기존 파일 삭제 시도 (덮어쓰기 준비)
                delete_url = f"{STORAGE_API_URL}/{BUCKET_NAME}/{filename}"
                try:
                    delete_response = requests.delete(delete_url, headers=headers, timeout=30)
                    print(f"🗑️  기존 파일 삭제 시도: {delete_response.status_code}")
                except:
                    pass  # 파일이 없으면 무시
                
                # 새 파일 업로드 (메모리 바이트 직접 전송)
                upload_url = f"{STORAGE_API_URL}/{BUCKET_NAME}/{filename}"
                
                upload_response = requests.post(
                    upload_url,
                    headers=headers,
                    data=gif_bytes,  # 🚀 메모리 바이트 직접 전송
                    timeout=60
                )
                
                print(f"📤 업로드 응답: {upload_response.status_code}")
                
                if upload_response.status_code in [200, 201]:
                    print(f"✅ 메모리 직접 업로드 성공 (시도 {attempt})")
                    
                    # Public URL 생성
                    public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{filename}"
                    
                    print(f"🌐 Public URL 생성: {public_url}")
                    return public_url
                    
                else:
                    raise Exception(f"업로드 실패: HTTP {upload_response.status_code} - {upload_response.text}")
                    
            except Exception as attempt_error:
                last_error = attempt_error
                print(f"❌ 업로드 시도 {attempt} 실패: {str(attempt_error)}")
                
                if attempt < retries:
                    wait_time = attempt * 2  # 2초, 4초, 6초...
                    print(f"⏳ {wait_time}초 후 재시도...")
                    time.sleep(wait_time)
        
        # 모든 재시도 실패
        raise Exception(f"{retries}번 시도 후 업로드 실패: {str(last_error)}")
        
    except Exception as e:
        raise Exception(f"메모리 직접 업로드 실패: {str(e)}")

# 🔧 Leapcell: 메모리 정리 함수 추가
def cleanup_memory():
    """메모리 정리 함수 (Leapcell serverless 환경용)"""
    gc.collect()  # 가비지 컬렉션 강제 실행
    print("🧹 메모리 정리 완료")

def generate_complete_gif_with_upload(text, frame_count=20, frame_interval=150):
    """
    🚀 완전 메모리 기반 GIF 생성 + Supabase HTTP 업로드 통합 프로세스
    파일 시스템을 전혀 사용하지 않는 완전 메모리 처리
    
    Args:
        text (str): 사용자 입력 텍스트
        frame_count (int): 캡처할 프레임 수 (기본값: 20개)
        frame_interval (int): 프레임 간 간격 (밀리초, 기본값: 150ms)
    
    Returns:
        dict: 생성 및 업로드 결과 정보
    """
    images = []  # 정리할 이미지들
    
    try:
        print(f"🎬 완전 메모리 기반 GIF 생성 + HTTP 업로드 시작: {text[:30]}...")
        
        # 1단계: HTML 템플릿 생성
        print("📝 쇼핑몰형 HTML 템플릿 생성...")
        html_content = render_template_to_html(text)
        
        # 2단계: 🚀 브라우저 1개로 연속 캡처 (메모리에서만)
        print(f"🎨 브라우저 1개로 {frame_count}개 프레임 연속 캡처...")
        images = sync_capture_animation(html_content, frame_count, frame_interval)
        
        # 3단계: 🚀 메모리에서 GIF 생성 (파일 시스템 사용 안 함)
        print(f"🎬 메모리에서 {len(images)}개 프레임을 GIF로 합성...")
        gif_bytes = create_gif_from_frames_in_memory(images, duration=frame_interval)
        gif_size = len(gif_bytes)
        
        # 4단계: 🚀 메모리 바이트를 직접 Supabase 업로드
        print("📤 메모리 GIF 바이트를 Supabase에 직접 업로드...")
        public_url = upload_gif_bytes_to_supabase(gif_bytes)
        
        # 5단계: 결과 정보 수집
        total_duration = len(images) * frame_interval
        result = {
            'success': True,
            'public_url': public_url,
            'gif_size': gif_size,
            'frames_generated': len(images),
            'duration_per_frame': frame_interval,
            'total_duration': total_duration,
            'loop_count': 'infinite',
            'upload_success': True,
            'filename': 'bg1.gif',
            'capture_method': 'browser_1x_continuous',
            'animation_type': 'css_pulse_wave',
            'processing_method': 'full_memory_based'  # 🚀 완전 메모리 처리 표시
        }
        
        print(f"🎉 완전 메모리 기반 GIF 생성 + HTTP 업로드 성공!")
        print(f"🌐 Public URL: {public_url}")
        print(f"📊 {len(images)}프레임, {total_duration}ms, {gif_size} bytes")
        
        return result
        
    except Exception as e:
        print(f"❌ 완전 메모리 기반 GIF 생성 + HTTP 업로드 실패: {str(e)}")
        raise Exception(f"완전한 GIF 생성 + HTTP 업로드 실패: {str(e)}")
    
    finally:
        # 이미지 객체들 정리
        print("🧹 이미지 객체 정리 중...")
        for img in images:
            try:
                img.close()
            except Exception as cleanup_error:
                print(f"⚠️  이미지 정리 실패: {cleanup_error}")
        
        # 🔧 Leapcell: 메모리 정리 추가
        cleanup_memory()

# =================================
# Flask 라우트들 (기존과 동일)
# =================================

@app.route('/')
def index():
    """메인 페이지 - index.html로 리다이렉트"""
    return send_from_directory('static', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """정적 파일 서빙"""
    try:
        return send_from_directory('static', filename)
    except:
        return "파일을 찾을 수 없습니다.", 404

# API 라우트들
@app.route('/api/health', methods=['GET'])
def health_check():
    """서버 상태 확인 API"""
    supabase_connected = test_supabase_connection()
    
    return jsonify({
        'status': 'OK',
        'message': 'THE BLACK SHOP GIF Generator 서버가 정상 작동 중입니다!',
        'version': '7.0.0',  # 🚀 완전 메모리 처리 업그레이드
        'functions': [
            'render_template_to_html', 
            'capture_animation_frames',        # 🚀 브라우저 1개 연속 캡처
            'sync_capture_animation',          # 🚀 동기 래퍼
            'create_gif_from_frames_in_memory', # 🚀 메모리 GIF 생성
            'upload_gif_bytes_to_supabase',    # 🚀 메모리 직접 업로드
            'generate_complete_gif_with_upload'
        ],
        'supabase_connected': supabase_connected,
        'dependencies': 'greenlet-free (requests only)',
        'platform': 'Leapcell Serverless',
        'capture_method': 'browser_1x_continuous_memory',  # 🚀 완전 메모리 처리
        'animation_support': 'css_pulse_wave_20fps',       # 🚀 20프레임 지원
        'file_system': 'memory_only_no_disk'               # 🚀 디스크 사용 안 함
    })

@app.route('/api/generate-gif', methods=['POST'])
def generate_gif_api():
    """🚀 개선된 GIF 생성 API - 브라우저 1개 방식 + 쇼핑몰 템플릿"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        # 선택적 파라미터들 (기본값 있음)
        frame_count = data.get('frame_count', 20)  # 20프레임 기본
        frame_interval = data.get('frame_interval', 150)  # 150ms 간격 기본
        
        if not text:
            return jsonify({
                'success': False,
                'error': '텍스트를 입력해주세요.'
            }), 400
        
        print(f"🎬 브라우저 1개 방식 GIF 생성 요청: {text[:50]}...")
        print(f"⚙️  설정: {frame_count}프레임, {frame_interval}ms 간격")
        
        try:
            # 🚀 완전히 개선된 GIF 생성 + HTTP 업로드 실행
            result = generate_complete_gif_with_upload(text, frame_count, frame_interval)
            
            # 성공 응답
            return jsonify({
                'success': True,
                'gifUrl': result['public_url'],  # 실제 Supabase Public URL
                'fileName': result['filename'],
                'fileSize': f"{result['gif_size']} bytes",
                'htmlCode': f'<img src="{result["public_url"]}" alt="THE BLACK SHOP GIF" style="max-width:100%; height:auto; border-radius:12px; display: block; margin: 0 auto;">',
                'generation_info': {
                    'frames': result['frames_generated'],
                    'duration_per_frame': f"{result['duration_per_frame']}ms",
                    'total_duration': f"{result['total_duration']}ms",
                    'loop': result['loop_count'],
                    'uploaded_to_supabase': result['upload_success'],
                    'method': result['capture_method'],        # 🚀 브라우저 1개 방식 표시
                    'animation_type': result['animation_type'], # 🚀 CSS 펄스 애니메이션
                    'processing': result['processing_method'],  # 🚀 완전 메모리 처리
                    'platform': 'Leapcell Serverless'
                }
            })
            
        except Exception as generation_error:
            return jsonify({
                'success': False,
                'error': f'GIF 생성 중 오류: {str(generation_error)}'
            }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'서버 오류: {str(e)}'
        }), 500

@app.route('/temp/<filename>')
def serve_temp_file(filename):
    """임시 파일 서빙 (개발용)"""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    try:
        return send_from_directory(temp_dir, filename)
    except:
        return "파일을 찾을 수 없습니다.", 404

# 🔧 Leapcell: Flask 실행 부분 완전 수정
if __name__ == '__main__':
    # 환경변수에서 포트 읽기 (Leapcell용)
    port = int(os.getenv('PORT', 5000))
    
    print("🚀 THE BLACK SHOP GIF Generator 서버 시작! (완전 메모리 처리)")
    print(f"📡 포트: {port}")
    print("📁 정적 파일: static 폴더")
    print("📝 템플릿 파일: templates 폴더")
    print("🎭 Playwright: 브라우저 1개 연속 캡처 준비")
    print("🎨 Pillow: 20프레임 메모리 이미지 처리 준비")
    print("📤 Supabase: 메모리 바이트 직접 업로드 (greenlet-free)")
    print("🌊 CSS 펄스 파도 애니메이션 지원")
    print("💾 완전 메모리 기반 처리 (디스크 사용 안 함)")
    print("🌐 Leapcell 서버리스 환경 최적화")
    
    # Supabase 연결 테스트
    print("🔍 Supabase 연결 테스트...")
    if test_supabase_connection():
        print("✅ Supabase 연결 확인 완료")
    else:
        print("⚠️  Supabase 연결 문제 (서버는 계속 실행)")
    
    print("✅ Flask 서버 실행 중...")
    print("🎉 완전 메모리 기반 + 쇼핑몰 펄스 애니메이션 완성!")
    
    # Leapcell 환경 맞춤 실행
    app.run(
        debug=False,  # 🔧 Production 모드
        host='0.0.0.0',  # 모든 IP에서 접근 가능
        port=port  # 🔧 동적 포트
    )
