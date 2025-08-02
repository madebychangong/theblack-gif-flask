/**
 * GIF 합성 및 Supabase 업로드 클래스
 * 
 * 사용법:
 * 1. GIFComposer 인스턴스 생성
 * 2. generateGIF() 호출
 * 3. 진행상황 콜백으로 UI 업데이트
 */

class GIFComposer {
  constructor(supabaseConfig) {
    this.supabaseUrl = 'https://ssnmitgehgzzcpmqwhzt.supabase.co';
    this.supabaseKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNzbm1pdGdlaGd6emNwbXF3aHp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMzNjI1MDgsImV4cCI6MjA2ODkzODUwOH0.u3FrSDh5qYeccQmn0PkOs4nfqIhXLSFHhpWj2JXhTrA';
    this.bucketName = supabaseConfig.bucketName || 'changong-images';
    
    // gif.js는 CDN에서 로드되어야 함
    this.gifWorkerScript = 'https://cdnjs.cloudflare.com/ajax/libs/gif.js/0.2.0/gif.worker.js';
  }

  /**
   * 메인 GIF 생성 함수
   * @param {string} text - 사용자 입력 텍스트
   * @param {Object} callbacks - 진행상황 콜백들
   * @returns {Promise<Object>} 결과 정보
   */
  async generateGIF(text, callbacks = {}) {
    const {
      onProgress = () => {},
      onFramesReceived = () => {},
      onGIFCreated = () => {},
      onUploaded = () => {},
      onError = () => {}
    } = callbacks;

    try {
      // 1단계: 서버리스 함수에서 프레임 받기
      onProgress('프레임 생성 요청 중...', 10);
      
      const frames = await this.requestFrames(text);
      onFramesReceived(frames);
      onProgress('프레임 수신 완료!', 30);

      // 2단계: 클라이언트에서 GIF 합성
      onProgress('GIF 합성 중...', 50);
      
      const gifBlob = await this.createGIF(frames, (progress) => {
        onProgress(`GIF 합성 중... ${Math.round(progress)}%`, 50 + (progress * 0.3));
      });
      
      onGIFCreated(gifBlob);
      onProgress('GIF 생성 완료!', 80);

      // 3단계: Supabase 업로드
      onProgress('업로드 중...', 85);
      
      const uploadResult = await this.uploadToSupabase(gifBlob);
      onUploaded(uploadResult);
      onProgress('업로드 완료!', 100);

      return {
        success: true,
        ...uploadResult,
        gifBlob,
        frameCount: frames.length
      };

    } catch (error) {
      console.error('GIF 생성 실패:', error);
      onError(error);
      throw error;
    }
  }

  /**
   * 서버리스 함수에서 프레임 요청
   * @param {string} text - 사용자 텍스트
   * @returns {Promise<Array>} Base64 이미지 배열
   */
  async requestFrames(text) {
    console.log('🔄 프레임 요청 시작:', text);
    
    const response = await fetch('/.netlify/functions/generate-frames', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text })
    });

    console.log('📡 응답 상태:', response.status, response.statusText);
    console.log('📡 응답 헤더:', Object.fromEntries(response.headers.entries()));

    if (!response.ok) {
      let errorMessage = `서버 오류 (${response.status})`;
      
      try {
        const errorText = await response.text();
        console.error('❌ 에러 응답 내용:', errorText);
        
        if (errorText.trim().startsWith('{')) {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.error || errorMessage;
        } else {
          errorMessage = errorText || errorMessage;
        }
      } catch (parseError) {
        console.error('❌ 에러 응답 파싱 실패:', parseError);
      }
      
      throw new Error(errorMessage);
    }

    // 응답 내용 확인
    const responseText = await response.text();
    console.log('📄 원본 응답 내용:', responseText);

    if (!responseText.trim()) {
      throw new Error('서버에서 빈 응답을 받았습니다.');
    }

    let data;
    try {
      data = JSON.parse(responseText);
    } catch (jsonError) {
      console.error('❌ JSON 파싱 에러:', jsonError);
      console.error('❌ 응답 내용:', responseText);
      throw new Error('서버 응답이 유효한 JSON 형식이 아닙니다.');
    }
    
    if (!data.success) {
      throw new Error(data.error || '프레임 생성 실패');
    }

    console.log('✅ 프레임 요청 성공:', data.frames.length, '개');
    return data.frames;
  }

  /**
   * 프레임들을 GIF로 합성
   * @param {Array} frames - Base64 이미지 배열
   * @param {Function} onProgress - 진행률 콜백
   * @returns {Promise<Blob>} GIF Blob
   */
  async createGIF(frames, onProgress = () => {}) {
    return new Promise((resolve, reject) => {
      // gif.js 설정
      const gif = new GIF({
        workers: 2,           // 워커 개수
        quality: 10,          // 품질 (1-30, 낮을수록 고품질)
        width: 720,           // 템플릿 크기
        height: 900,
        workerScript: this.gifWorkerScript,
        background: '#000000' // 배경색
      });

      // 진행률 추적
      gif.on('progress', (progress) => {
        onProgress(progress * 100);
      });

      // 완료 처리
      gif.on('finished', (blob) => {
        console.log('✅ GIF 합성 완료, 크기:', this.formatFileSize(blob.size));
        resolve(blob);
      });

      // 에러 처리
      gif.on('error', (error) => {
        console.error('❌ GIF 합성 실패:', error);
        reject(new Error('GIF 합성 실패: ' + error.message));
      });

      // 프레임들을 이미지로 변환하여 추가
      Promise.all(frames.map(frameData => this.loadImage(frameData)))
        .then(images => {
          images.forEach((img, index) => {
            console.log(`📸 프레임 ${index + 1} 추가 중...`);
            gif.addFrame(img, {
              delay: 800,  // 0.8초 간격 (원본과 동일)
              copy: true
            });
          });

          console.log('🎬 GIF 렌더링 시작...');
          gif.render();
        })
        .catch(reject);
    });
  }

  /**
   * Base64 이미지를 Image 객체로 변환
   * @param {string} base64Data - Base64 이미지 데이터
   * @returns {Promise<HTMLImageElement>}
   */
  loadImage(base64Data) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('이미지 로딩 실패'));
      img.src = base64Data;
    });
  }

  /**
   * Supabase Storage에 GIF 업로드
   * @param {Blob} gifBlob - GIF 파일 Blob
   * @returns {Promise<Object>} 업로드 결과
   */
  async uploadToSupabase(gifBlob) {
    const fileName = `theblack_${Date.now()}.gif`;
    const formData = new FormData();
    formData.append('file', gifBlob, fileName);

    // Supabase Storage API 직접 호출
    const uploadResponse = await fetch(
      `${this.supabaseUrl}/storage/v1/object/${this.bucketName}/${fileName}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.supabaseKey}`,
        },
        body: formData
      }
    );

    if (!uploadResponse.ok) {
      const errorText = await uploadResponse.text();
      throw new Error(`업로드 실패: ${errorText}`);
    }

    // 공개 URL 생성
    const publicUrl = `${this.supabaseUrl}/storage/v1/object/public/${this.bucketName}/${fileName}`;
    
    console.log('📤 Supabase 업로드 완료:', publicUrl);

    return {
      fileName,
      fileSize: this.formatFileSize(gifBlob.size),
      gifUrl: publicUrl,
      htmlCode: this.generateHTMLCode(publicUrl)
    };
  }

  /**
   * 파일 크기를 읽기 쉬운 형태로 변환
   * @param {number} bytes - 바이트 크기
   * @returns {string} 포맷된 크기
   */
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * HTML 임베드 코드 생성
   * @param {string} gifUrl - GIF URL
   * @returns {string} HTML 코드
   */
  generateHTMLCode(gifUrl) {
    return `<img src="${gifUrl}" alt="THE BLACK SHOP GIF" style="max-width: 100%; height: auto; border-radius: 8px;">`;
  }
}

/**
 * Supabase 설정 예시:
 * 
 * const supabaseConfig = {
 *   url: 'https://your-project.supabase.co',
 *   key: 'your-anon-key',
 *   bucketName: 'gifs'
 * };
 * 
 * const composer = new GIFComposer(supabaseConfig);
 * 
 * composer.generateGIF('텍스트 내용', {
 *   onProgress: (message, percent) => console.log(message, percent + '%'),
 *   onError: (error) => console.error('오류:', error)
 * }).then(result => {
 *   console.log('성공:', result);
 * });
 */

// 전역으로 사용할 수 있게 export
window.GIFComposer = GIFComposer;