from flask import Flask, request, jsonify, send_from_directory, render_template_string
import os
import asyncio
import time
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from PIL import Image
from supabase import create_client, Client

# 환경변수 로드
load_dotenv()

app = Flask(__name__)

# =================================
# Supabase 설정
# =================================

# Supabase 클라이언트 초기화
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ssnmitgehgzzcpmqwhzt.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNzbm1pdGdlaGd6emNwbXF3aHp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMzNjI1MDgsImV4cCI6MjA2ODkzODUwOH0.u3FrSDh5qYeccQmn0PkOs4nfqIhXLSFHhpWj2JXhTrA')

print(f"🔗 Supabase URL: {SUPABASE_URL}")
print(f"🔐 Supabase Key: {SUPABASE_KEY[:20]}...")

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase 클라이언트 초기화 성공")
except Exception as e:
    print(f"❌ Supabase 클라이언트 초기화 실패: {e}")
    supabase = None

# =================================
# GIF 생성 핵심 함수들
# =================================

def render_template_to_html(text, frame_number):
    """
    사용자 텍스트와 프레임 번호를 받아서 완성된 HTML 문자열 생성
    
    Args:
        text (str): 사용자가 입력한 텍스트
        frame_number (int): 프레임 번호 (1, 2, 3, 4)
    
    Returns:
        str: 완성된 HTML 문자열
    """
    try:
        # 1. 줄바꿈을 HTML <br> 태그로 변환
        formatted_text = text.replace('\n', '<br>')
        
        # 2. 프레임 클래스 설정
        frame_class = f"frame-{frame_number}"
        
        # 3. 템플릿 파일 읽기
        template_path = os.path.join('templates', 'theblackempty.html')
        with open(template_path, 'r', encoding='utf-8') as file:
            template_content = file.read()
        
        # 4. Flask 템플릿 엔진으로 HTML 생성
        html_content = render_template_string(
            template_content,
            text=formatted_text,
            frame_class=frame_class
        )
        
        return html_content
        
    except Exception as e:
        raise Exception(f"HTML 템플릿 생성 실패: {str(e)}")

async def capture_frame_with_playwright(html_content, output_path):
    """
    HTML 콘텐츠를 Playwright로 브라우저에 로드하고 스크린샷 촬영
    
    Args:
        html_content (str): 렌더링할 HTML 문자열
        output_path (str): 저장할 PNG 파일 경로
    
    Returns:
        str: 생성된 파일 경로
    """
    browser = None
    try:
        print(f"📸 Playwright 캡처 시작: {os.path.basename(output_path)}")
        
        # 1. Playwright 브라우저 실행
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            
            # 2. 새 페이지 생성
            page = await browser.new_page()
            
            # 3. 뷰포트 크기 설정 (720x900)
            await page.set_viewport_size({"width": 720, "height": 900})
            
            # 4. HTML 콘텐츠 로드
            await page.set_content(html_content, wait_until='networkidle')
            
            # 5. 폰트 로딩 대기 (Google Fonts)
            await page.wait_for_timeout(2000)  # 2초 대기
            
            # 6. 폰트 완전 로드 확인
            await page.evaluate("document.fonts.ready")
            
            # 7. render-target 요소 찾기
            render_target = await page.query_selector('.render-target')
            if not render_target:
                raise Exception("render-target 요소를 찾을 수 없습니다")
            
            # 8. 요소의 실제 크기 계산
            box = await render_target.bounding_box()
            if not box:
                raise Exception("render-target 요소의 크기를 계산할 수 없습니다")
            
            # 9. 스크린샷 촬영
            await render_target.screenshot(
                path=output_path,
                type='png'
            )
            
            await browser.close()
            
        # 10. 파일 존재 확인
        if not os.path.exists(output_path):
            raise Exception("스크린샷 파일이 생성되지 않았습니다")
        
        file_size = os.path.getsize(output_path)
        print(f"✅ 캡처 완료: {os.path.basename(output_path)} ({file_size} bytes)")
        
        return output_path
        
    except Exception as e:
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        # 실패한 파일 정리
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
                
        raise Exception(f"Playwright 캡처 실패: {str(e)}")

def sync_capture_frame(html_content, output_path):
    """
    비동기 capture_frame_with_playwright를 동기적으로 실행하는 래퍼 함수
    """
    try:
        # 새 이벤트 루프에서 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                capture_frame_with_playwright(html_content, output_path)
            )
            return result
        finally:
            loop.close()
    except Exception as e:
        raise Exception(f"동기 캡처 실행 실패: {str(e)}")

def create_gif_from_frames(frame_paths, output_gif_path, duration=800):
    """
    4개의 PNG 프레임을 하나의 애니메이션 GIF로 합성
    
    Args:
        frame_paths (list): PNG 파일 경로들의 리스트
        output_gif_path (str): 생성될 GIF 파일 경로
        duration (int): 각 프레임 지속 시간 (밀리초, 기본값: 800ms)
    
    Returns:
        str: 생성된 GIF 파일 경로
    """
    try:
        print(f"🎨 GIF 생성 시작: {os.path.basename(output_gif_path)}")
        
        # 1. 모든 프레임 파일 존재 확인
        images = []
        for i, frame_path in enumerate(frame_paths):
            if not os.path.exists(frame_path):
                raise Exception(f"프레임 파일이 존재하지 않습니다: {frame_path}")
            
            try:
                img = Image.open(frame_path)
                # RGBA 모드로 변환 (투명도 지원)
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                images.append(img)
                print(f"📷 프레임 {i+1} 로드: {img.size}")
            except Exception as e:
                raise Exception(f"프레임 {i+1} 로드 실패: {str(e)}")
        
        if len(images) != 4:
            raise Exception(f"4개의 프레임이 필요하지만 {len(images)}개만 로드됨")
        
        # 2. 첫 번째 이미지를 기준으로 GIF 생성
        first_image = images[0]
        other_images = images[1:]
        
        # 3. GIF로 저장
        first_image.save(
            output_gif_path,
            save_all=True,
            append_images=other_images,
            duration=duration,  # 각 프레임 지속 시간 (ms)
            loop=0,  # 무한 반복
            optimize=True,  # 파일 크기 최적화
            format='GIF'
        )
        
        # 4. 생성된 파일 확인
        if not os.path.exists(output_gif_path):
            raise Exception("GIF 파일이 생성되지 않았습니다")
        
        file_size = os.path.getsize(output_gif_path)
        print(f"✅ GIF 생성 완료: {os.path.basename(output_gif_path)} ({file_size} bytes)")
        
        # 5. 이미지 객체 정리
        for img in images:
            img.close()
        
        return output_gif_path
        
    except Exception as e:
        # 이미지 객체 정리
        for img in images:
            try:
                img.close()
            except:
                pass
        
        # 실패한 GIF 파일 정리
        if os.path.exists(output_gif_path):
            try:
                os.remove(output_gif_path)
            except:
                pass
                
        raise Exception(f"GIF 생성 실패: {str(e)}")

def upload_gif_to_supabase(gif_file_path, retries=3):
    """
    GIF 파일을 Supabase Storage에 업로드하고 Public URL 반환
    
    Args:
        gif_file_path (str): 업로드할 GIF 파일 경로
        retries (int): 실패시 재시도 횟수
    
    Returns:
        str: Public URL
    """
    if not supabase:
        raise Exception("Supabase 클라이언트가 초기화되지 않았습니다")
    
    try:
        print(f"📤 Supabase 업로드 시작: {os.path.basename(gif_file_path)}")
        
        # 1. 파일 존재 확인
        if not os.path.exists(gif_file_path):
            raise Exception(f"업로드할 파일이 존재하지 않습니다: {gif_file_path}")
        
        # 2. 고유한 파일명 생성 (원본명)
        unique_filename = "bg1.gif"
        
        # 3. 파일 읽기
        with open(gif_file_path, 'rb') as file:
            file_data = file.read()
        
        file_size = len(file_data)
        print(f"📦 업로드 준비: {unique_filename} ({file_size} bytes)")
        
        # 4. 재시도 로직으로 업로드
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                print(f"🔄 업로드 시도 {attempt}/{retries}")
                
                # 기존 파일 삭제 시도 (덮어쓰기 준비)
                try:
                    supabase.storage.from_('changong-images').remove([unique_filename])
                except:
                    pass  # 파일이 없으면 무시
                
                # 파일 업로드
                result = supabase.storage.from_('changong-images').upload(
                    unique_filename,
                    file_data,
                    {
                        'content-type': 'image/gif',
                        'cache-control': '3600',
                        'upsert': 'true'
                    }
                )
                
                print(f"✅ 업로드 성공 (시도 {attempt})")
                
                # 5. Public URL 생성
                public_url_response = supabase.storage.from_('changong-images').get_public_url(unique_filename)
                public_url = public_url_response
                
                if not public_url:
                    raise Exception("Public URL 생성 실패")
                
                print(f"🌐 Public URL 생성: {public_url}")
                
                return public_url
                
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
        raise Exception(f"Supabase 업로드 실패: {str(e)}")

def generate_complete_gif_with_upload(text):
    """
    전체 GIF 생성 + Supabase 업로드 통합 프로세스
    
    Args:
        text (str): 사용자 입력 텍스트
    
    Returns:
        dict: 생성 및 업로드 결과 정보
    """
    temp_files = []  # 정리할 임시 파일들
    local_gif_path = None
    
    try:
        print(f"🎬 완전한 GIF 생성 + 업로드 시작: {text[:30]}...")
        
        # temp 폴더 확인
        temp_dir = os.path.join(os.getcwd(), 'temp')
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        timestamp = int(time.time())
        frame_paths = []
        
        # 1단계: 4개 프레임 모두 생성
        print("📸 4개 프레임 캡처 시작...")
        for frame in range(1, 5):
            print(f"🎭 프레임 {frame}/4 생성 중...")
            
            # 1-1. HTML 템플릿 생성
            html_content = render_template_to_html(text, frame)
            
            # 1-2. PNG 캡처
            frame_filename = f"frame_{timestamp}_{frame}.png"
            frame_path = os.path.join(temp_dir, frame_filename)
            temp_files.append(frame_path)
            
            sync_capture_frame(html_content, frame_path)
            frame_paths.append(frame_path)
            
            print(f"✅ 프레임 {frame} 완료")
        
        # 2단계: GIF 합성
        print("🎨 4개 프레임을 GIF로 합성...")
        gif_filename = f"theblack_gif_{timestamp}.gif"
        local_gif_path = os.path.join(temp_dir, gif_filename)
        
        create_gif_from_frames(frame_paths, local_gif_path, duration=800)
        local_gif_size = os.path.getsize(local_gif_path)
        
        # 3단계: Supabase 업로드
        print("📤 Supabase 업로드 시작...")
        public_url = upload_gif_to_supabase(local_gif_path)
        
        # 4단계: 결과 정보 수집
        result = {
            'success': True,
            'public_url': public_url,
            'local_path': local_gif_path,
            'gif_size': local_gif_size,
            'frames_generated': len(frame_paths),
            'duration_per_frame': 800,
            'total_duration': 800 * 4,
            'loop_count': 'infinite',
            'upload_success': True,
            'filename': gif_filename
        }
        
        print(f"🎉 GIF 생성 + 업로드 완전 성공!")
        print(f"🌐 Public URL: {public_url}")
        
        return result
        
    except Exception as e:
        print(f"❌ GIF 생성 + 업로드 실패: {str(e)}")
        
        raise Exception(f"완전한 GIF 생성 + 업로드 실패: {str(e)}")
    
    finally:
        # 임시 프레임 파일들 정리
        print("🧹 임시 파일 정리 중...")
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    print(f"🗑️  정리: {os.path.basename(temp_file)}")
            except Exception as cleanup_error:
                print(f"⚠️  정리 실패: {temp_file} - {cleanup_error}")
        
        # 로컬 GIF 파일도 정리 (선택적)
        # if local_gif_path and os.path.exists(local_gif_path):
        #     try:
        #         os.remove(local_gif_path)
        #         print(f"🗑️  로컬 GIF 정리: {os.path.basename(local_gif_path)}")
        #     except:
        #         pass

# =================================
# Flask 라우트들
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
    return jsonify({
        'status': 'OK',
        'message': 'THE BLACK GIF Generator 서버가 정상 작동 중입니다!',
        'version': '4.0.0',
        'functions': [
            'render_template_to_html', 
            'capture_frame_with_playwright',
            'create_gif_from_frames',
            'upload_gif_to_supabase',
            'generate_complete_gif_with_upload'
        ],
        'supabase_connected': supabase is not None
    })

@app.route('/api/generate-gif', methods=['POST'])
def generate_gif_api():
    """GIF 생성 API - Supabase 업로드 포함 완전한 기능"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({
                'success': False,
                'error': '텍스트를 입력해주세요.'
            }), 400
        
        if not supabase:
            return jsonify({
                'success': False,
                'error': 'Supabase 연결이 설정되지 않았습니다.'
            }), 500
        
        print(f"🎬 GIF 생성 + 업로드 요청: {text[:50]}...")
        
        try:
            # 완전한 GIF 생성 + 업로드 실행
            result = generate_complete_gif_with_upload(text)
            
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
                    'uploaded_to_supabase': result['upload_success']
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

if __name__ == '__main__':
    print("🚀 THE BLACK GIF Generator 서버 시작!")
    print("📡 접속 주소: http://localhost:5000")
    print("📁 정적 파일: static 폴더")
    print("📝 템플릿 파일: templates 폴더")
    print("🎭 Playwright: 브라우저 자동화 준비")
    print("🎨 Pillow: 이미지 처리 준비")
    print("📤 Supabase: 파일 업로드 준비")
    
    # 기본적인 폴더 확인
    temp_dir = os.path.join(os.getcwd(), 'temp')
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        print(f"📁 temp 폴더 생성: {temp_dir}")
    else:
        print(f"📁 temp 폴더 확인: {temp_dir}")
    
    print("✅ Flask 개발 서버 실행 중...")
    print("🎉 완전한 GIF 생성 + Supabase 업로드 기능 준비 완료!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)